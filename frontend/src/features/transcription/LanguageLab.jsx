import { useEffect, useRef, useState } from "react";

import { createTranscription } from "../../api/client";
import { useWavRecorder } from "../../hooks/useWavRecorder";

const LANGUAGES = [
  { code: "ig", name: "Igbo", model: "Igbo-ASR" },
  { code: "ha", name: "Hausa", model: "Hausa-ASR" },
  { code: "yo", name: "Yoruba", model: "Yoruba-ASR" },
  { code: "en", name: "Nigerian English", model: "NigerianAccentedEnglish" },
];

export function LanguageLab() {
  const [language, setLanguage] = useState(LANGUAGES[0]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const timerRef = useRef(null);
  const { isRecording, start, stop } = useWavRecorder();

  useEffect(() => () => window.clearInterval(timerRef.current), []);

  async function startRecording() {
    setError("");
    setResult(null);
    setSeconds(0);
    try {
      await start();
      timerRef.current = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    } catch (recordingError) {
      setError(recordingError.message);
    }
  }

  async function stopAndTranscribe() {
    window.clearInterval(timerRef.current);
    setIsSubmitting(true);
    setError("");
    try {
      const audio = await stop();
      setResult(await createTranscription({ audio, language: language.code }));
    } catch (transcriptionError) {
      setError(transcriptionError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="languageLab" aria-labelledby="language-lab-title">
      <div className="languageLabHeader">
        <div>
          <p className="eyebrow">Live model evidence</p>
          <h2 id="language-lab-title">N-ATLaS Language Lab</h2>
          <p>Speak a short emergency report and include a street, landmark, or postcode.</p>
        </div>
        <span className="modelBadge">N-ATLaS ASR</span>
      </div>

      <div className="languageChoices" aria-label="Transcription language">
        {LANGUAGES.map((option) => (
          <button
            className={option.code === language.code ? "languageChoice languageChoice--active" : "languageChoice"}
            disabled={isRecording || isSubmitting}
            key={option.code}
            onClick={() => setLanguage(option)}
            type="button"
          >
            <strong>{option.name}</strong>
            <span>NCAIR1/{option.model}</span>
          </button>
        ))}
      </div>

      <div className="recordingControls">
        {isRecording ? (
          <button className="recordButton recordButton--stop" onClick={stopAndTranscribe} type="button">
            <span aria-hidden="true" /> Stop and transcribe · {seconds}s
          </button>
        ) : (
          <button className="recordButton" disabled={isSubmitting} onClick={startRecording} type="button">
            <span aria-hidden="true" /> {isSubmitting ? "Transcribing…" : `Speak ${language.name}`}
          </button>
        )}
        <p>16 kHz mono WAV · sent directly to the selected model</p>
      </div>

      {error && <div className="transcriptionError" role="alert">{error}</div>}
      {result && (
        <article className="transcriptResult" aria-live="polite">
          <div className="resultMeta">
            <span className={result.fallback_used ? "resultStatus resultStatus--fallback" : "resultStatus"}>
              {result.fallback_used ? "Fallback used" : "N-ATLaS verified"}
            </span>
            <span>{result.elapsed_ms.toLocaleString()} ms</span>
          </div>
          <blockquote>{result.text}</blockquote>
          <dl>
            <div><dt>Provider</dt><dd>{result.provider}</dd></div>
            <div><dt>Model</dt><dd>{result.model}</dd></div>
            <div><dt>Language</dt><dd>{language.name}</dd></div>
          </dl>
        </article>
      )}

      <p className="pidginNote">
        <strong>Pidgin:</strong> supported through Aabo's fallback path, but not labeled as N-ATLaS;
        the official N-ATLaS ASR set currently covers these four languages.
      </p>
    </section>
  );
}
