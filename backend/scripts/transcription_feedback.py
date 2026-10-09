"""Review and export consented ASR corrections for offline model work.

The export is never automatic. Only explicitly consented and manually approved
incidents are written. JSONL records still contain sensitive spoken content and
must remain inside the approved training environment.
"""

import argparse
import json
from pathlib import Path

from app.database import get_database
from app.repositories.incidents import IncidentRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List feedback awaiting human review")

    review = commands.add_parser("review", help="Approve or reject one incident")
    review.add_argument("incident_id")
    review.add_argument("decision", choices=("approved", "rejected"))

    export = commands.add_parser("export", help="Export approved examples as JSONL")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument(
        "--acknowledge-sensitive-data",
        action="store_true",
        help="Confirm that the output will stay in an approved training environment",
    )
    return parser


def _list_pending(repository: IncidentRepository) -> None:
    records = repository.list_transcription_feedback("pending")
    if not records:
        print("No consented feedback is awaiting review.")
        return
    for record in records:
        changed = record["original_transcript"] != record["transcript"]
        print(
            f"{record['id']}  {record['created_at']}  {record['language']}  "
            f"correction={'yes' if changed else 'no'}"
        )


def _export(repository: IncidentRepository, output: Path) -> None:
    records = repository.list_transcription_feedback("approved")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    {
                        "id": record["id"],
                        "language": record["language"],
                        "audio_filepath": record["recording_path"],
                        "audio_content_type": record["recording_content_type"],
                        "baseline_text": record["original_transcript"],
                        "text": record["transcript"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"Exported {len(records)} approved examples to {output}")


def main() -> None:
    arguments = _parser().parse_args()
    database = get_database()
    database.migrate()
    repository = IncidentRepository(database)

    if arguments.command == "list":
        _list_pending(repository)
        return
    if arguments.command == "review":
        if not repository.set_training_review_status(
            arguments.incident_id, arguments.decision
        ):
            raise SystemExit("Incident not found or training consent was not granted.")
        print(f"{arguments.incident_id}: {arguments.decision}")
        return
    if not arguments.acknowledge_sensitive_data:
        raise SystemExit("Export requires --acknowledge-sensitive-data")
    _export(repository, arguments.output)


if __name__ == "__main__":
    main()
