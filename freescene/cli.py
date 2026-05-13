"""Click-based CLI: ``freescene "story idea" --scenes 3 --style anime``."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from . import __version__
from .concat import FFmpegMissingError
from .config import Config
from .pipeline import make_movie
from .pricing import estimate as estimate_cost
from .render import RenderError


console = Console()

_STYLE_PRESETS = {
    "cinematic": "cinematic, warm, realistic",
    "anime": "anime, ghibli-inspired, soft",
    "documentary": "documentary, naturalistic, handheld",
    "noir": "noir, high-contrast, moody",
    "3d": "3d animation, pixar-style, vibrant",
    "vintage": "vintage 35mm film, grainy, nostalgic",
    "scifi": "sci-fi, neon, cyberpunk",
    "fantasy": "fantasy, ethereal, dreamlike",
}


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("idea", nargs=-1, required=True)
@click.option("-n", "--scenes", "num_scenes", type=click.IntRange(1, 12), default=3,
              show_default=True, help="Number of scene clips to render + stitch.")
@click.option("-s", "--style", default="cinematic", show_default=True,
              help=(
                  "Style preset or free-form style descriptor. Presets: "
                  + ", ".join(_STYLE_PRESETS.keys())
                  + ". Anything not listed is passed through verbatim."
              ))
@click.option("-d", "--duration", type=click.IntRange(2, 12), default=3,
              show_default=True,
              help=("Seconds per scene clip. The 3s default keeps a 3-scene "
                    "movie under the 30K-token free daily pool."))
@click.option("-m", "--video-model", default=None,
              help="Per-scene video model (env: VIDEO_MODEL).")
@click.option("--llm-model", default=None,
              help="Script-writing LLM (env: LLM_MODEL).")
@click.option("--api-url", default=None,
              help="OpenAI-compatible API root (env: FREE_API_URL).")
@click.option("--api-key", default=None,
              help="Bearer token for the API (env: FREE_API_KEY).")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path),
              default=None, help="Output .mp4 path. Default: ./<job_id>.mp4")
@click.option("--show-script", is_flag=True,
              help="Print the LLM-written scene prompts before rendering.")
@click.option("--dry-run", is_flag=True,
              help="Print the token-cost estimate and exit without rendering.")
@click.option("--quiet", is_flag=True, help="Suppress progress UI.")
@click.version_option(__version__, prog_name="freescene")
def main(
    idea: tuple[str, ...],
    num_scenes: int,
    style: str,
    duration: int,
    video_model: str | None,
    llm_model: str | None,
    api_url: str | None,
    api_key: str | None,
    output: Path | None,
    show_script: bool,
    dry_run: bool,
    quiet: bool,
) -> None:
    """Generate a multi-scene AI movie from a story idea.

    \b
    Examples:
      freescene "A retired astronaut tends a rooftop garden in Tokyo"
      freescene "Cyberpunk Tokyo at dawn" --scenes 5 --style scifi
      freescene "Pixar squirrel learns to surf" -n 4 -s 3d -d 6

    \b
    Backend defaults to https://api.free.ai (no key required up to the
    daily anonymous pool). Set FREE_API_KEY for your full account quota,
    or point at any OpenAI-compatible LLM + video API via FREE_API_URL.
    """
    idea_str = " ".join(idea).strip()
    if not idea_str:
        click.echo("Error: empty idea.", err=True)
        sys.exit(2)

    cfg = Config.from_env()
    if api_url:
        cfg.api_url = api_url
    if api_key:
        cfg.api_key = api_key
    if llm_model:
        cfg.llm_model = llm_model
    if video_model:
        cfg.video_model = video_model

    style_resolved = _STYLE_PRESETS.get(style.lower(), style)

    if output:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

    est = estimate_cost(num_scenes, duration)

    if not quiet:
        console.rule("[bold green]freescene")
        console.print(f"[dim]Idea:[/dim] {idea_str}")
        console.print(
            f"[dim]Scenes:[/dim] {num_scenes}  "
            f"[dim]Style:[/dim] {style_resolved}  "
            f"[dim]Duration/scene:[/dim] {duration}s"
        )
        console.print(
            f"[dim]LLM:[/dim] {cfg.llm_model}  "
            f"[dim]Video:[/dim] {cfg.video_model}  "
            f"[dim]Backend:[/dim] {cfg.effective_video_url}"
        )
        _key_status = (
            "[green]✓ API key set[/green]" if cfg.api_key
            else "[yellow]⚠ anonymous (no API key)[/yellow]"
        )
        console.print(
            f"[dim]Auth:[/dim] {_key_status}  "
            f"[dim]Est. cost:[/dim] {est.total_tokens:,} tokens "
            f"(~${est.usd_cost:.3f})"
        )
        console.print(f"[dim]Quota:[/dim] {est.hint}")

    if dry_run:
        if quiet:
            click.echo(str(est.total_tokens))
        else:
            console.print("\n[bold]Dry run — exiting without rendering.[/bold]")
        sys.exit(0)

    # Soft warn before anonymous users hit a guaranteed 402 — they pip-
    # installed, typed a command, and would otherwise watch the LLM call
    # succeed before the first scene render fails with "out of tokens".
    if not cfg.api_key and not est.affordable_with_anon and not quiet:
        console.print(
            "\n[bold yellow]Heads up:[/bold yellow] this request needs "
            f"{est.total_tokens:,} tokens but the anonymous daily pool is only "
            f"{2500:,}. The backend will return 402 Payment Required.\n"
            "Set [bold]FREE_API_KEY[/bold] (sign up free at https://free.ai/signup/ for "
            f"{5000:,} tokens/day, or buy a $5 pack for 200K tokens — about 40 scenes).\n"
            "Re-run with [bold]--dry-run[/bold] to see the estimate without spending."
        )
        if not click.confirm("Proceed anyway?", default=False):
            sys.exit(0)

    progress = None if quiet else Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )
    task_id = None
    if progress is not None:
        progress.start()
        task_id = progress.add_task("Starting…", total=num_scenes + 2)

    def _on_progress(phase: str, current: int, total: int, detail: str) -> None:
        labels = {
            "scriptwriting": "Writing scene script…",
            "scenes_ready": "Script ready, starting renders…",
            "rendering": f"Rendering scene {current}/{total}…",
            "concatenating": "Stitching scenes…",
            "done": "Done!",
        }
        label = labels.get(phase, phase)
        if progress is not None and task_id is not None:
            done_steps = {
                "scriptwriting": 0,
                "scenes_ready": 1,
                "rendering": 1 + current,
                "concatenating": 1 + total,
                "done": 2 + total,
            }.get(phase, 0)
            progress.update(task_id, description=label, completed=done_steps)

    try:
        result = make_movie(
            idea_str,
            num_scenes=num_scenes,
            style=style_resolved,
            duration_per_scene=duration,
            output_path=output,
            config=cfg,
            on_progress=_on_progress,
        )
    except FFmpegMissingError as e:
        if progress: progress.stop()
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(3)
    except RenderError as e:
        if progress: progress.stop()
        console.print(f"[bold red]Render failed:[/bold red] {e}")
        sys.exit(4)
    except Exception as e:
        if progress: progress.stop()
        console.print(f"[bold red]Failed:[/bold red] {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        if progress: progress.stop()

    if not quiet:
        console.rule("[bold green]Done")
        console.print(f"[bold]Output:[/bold] {result.output_path}")
        console.print(f"[dim]Job ID:[/dim] {result.job_id}  "
                      f"[dim]Elapsed:[/dim] {result.elapsed_s:.1f}s")
        if show_script:
            console.print("\n[bold]Scene script:[/bold]")
            for i, s in enumerate(result.scenes, 1):
                console.print(f"  [dim]{i}.[/dim] {s}")
    else:
        click.echo(str(result.output_path))


if __name__ == "__main__":
    main()
