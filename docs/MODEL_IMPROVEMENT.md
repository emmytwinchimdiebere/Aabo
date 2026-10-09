# Speech model improvement

Aabo preserves a potential supervised ASR example only when the caller opts in.
The example contains the original recording, the baseline N-ATLaS transcript,
the caller-corrected transcript, and the selected language. It is not sent to a
training service automatically.

## Review workflow

From `backend/`, list consented examples awaiting review:

```powershell
.\.venv\Scripts\python.exe scripts\transcription_feedback.py list
```

Listen to the original recording in the dispatcher console. Confirm that the
corrected transcript faithfully represents the audio and that the example is
appropriate for the approved training environment. Then approve or reject it:

```powershell
.\.venv\Scripts\python.exe scripts\transcription_feedback.py review inc_example approved
.\.venv\Scripts\python.exe scripts\transcription_feedback.py review inc_example rejected
```

Export only approved examples:

```powershell
.\.venv\Scripts\python.exe scripts\transcription_feedback.py export `
  --output .\data\approved-asr-feedback.jsonl `
  --acknowledge-sensitive-data
```

The JSONL contains references to the original audio and both transcript
versions. Emergency recordings can contain names, addresses, medical details,
and other sensitive information. Keep exports out of Git, restrict access, and
apply the project's retention and deletion rules. Use synthetic or otherwise
explicitly authorized examples for public evaluation and shared datasets.

## Evaluation before fine-tuning

Split approved examples by speaker, keep a held-out evaluation set, and report
word error rate separately for English, Hausa, Igbo, and Yoruba. Track address
and landmark accuracy as a second metric because ordinary word error rate can
hide the mistakes that matter most to dispatchers. Never train and evaluate on
different recordings from the same caller.
