import { useEffect, useRef, useState } from "react";

import { createTranscription, createWebIncident, extractLocation } from "../../api/client";
import { useWavRecorder } from "../../hooks/useWavRecorder";

const LANGUAGES = [
  { code: "ig", name: "Igbo", prompt: "Kọwaa ihe merenụ" },
  { code: "ha", name: "Hausa", prompt: "Faɗa mana abin da ya faru" },
  { code: "yo", name: "Yorùbá", prompt: "Sọ ohun tó ṣẹlẹ̀" },
  { code: "en", name: "English", prompt: "Tell us what happened" },
];

const EMERGENCY_TYPES = ["Medical", "Fire", "Security", "Accident", "Other"];
const MAX_RECORDING_SECONDS = 20;

function formatTime(seconds) {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function CallerVoiceReport() {
  const [language, setLanguage] = useState(LANGUAGES[0]);
  const [phase, setPhase] = useState("ready");
  const [seconds, setSeconds] = useState(0);
  const [audio, setAudio] = useState(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [rawTranscript, setRawTranscript] = useState("");
  const [confirmedTranscript, setConfirmedTranscript] = useState("");
  const [emergencyType, setEmergencyType] = useState("");
  const [address, setAddress] = useState("");
  const [coordinates, setCoordinates] = useState(null);
  const [locationState, setLocationState] = useState("idle");
  const [error, setError] = useState("");
  const [locationSuggestion, setLocationSuggestion] = useState("");
  const [incidentId, setIncidentId] = useState("");
  const [trainingConsent, setTrainingConsent] = useState(false);
  const timerRef = useRef(null);
  const autoStopRef = useRef(null);
  const finishingRef = useRef(false);
  const { isRecording, start, stop } = useWavRecorder();

  useEffect(() => () => {
    window.clearInterval(timerRef.current);
    window.clearTimeout(autoStopRef.current);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  async function beginRecording() {
    setError("");
    setSeconds(0);
    try {
      await start();
      finishingRef.current = false;
      setPhase("recording");
      timerRef.current = window.setInterval(() => setSeconds((value) => value + 1), 1000);
      autoStopRef.current = window.setTimeout(finishRecording, MAX_RECORDING_SECONDS * 1000);
    } catch (recordingError) {
      setError(recordingError.message);
    }
  }

  async function finishRecording() {
    if (finishingRef.current) return;
    finishingRef.current = true;
    window.clearInterval(timerRef.current);
    window.clearTimeout(autoStopRef.current);
    setPhase("transcribing");
    setError("");
    try {
      const recording = await stop();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudio(recording);
      setAudioUrl(URL.createObjectURL(recording));
      const result = await createTranscription({ audio: recording, language: language.code });
      setRawTranscript(result.text);
      setConfirmedTranscript(result.text);
      try {
        const extracted = await extractLocation({
          transcript: result.text,
          language: language.code,
        });
        if (extracted.address) {
          setAddress(extracted.address);
          setLocationSuggestion(extracted.address);
        }
        if (extracted.emergency_type) setEmergencyType(extracted.emergency_type);
      } catch {
        setLocationSuggestion("");
      }
      setPhase("review");
    } catch (transcriptionError) {
      setPhase("ready");
      setError(transcriptionError.message);
    }
  }

  function requestLocation() {
    if (!navigator.geolocation) {
      setLocationState("unavailable");
      return;
    }
    setLocationState("locating");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setCoordinates({ latitude: coords.latitude, longitude: coords.longitude });
        setLocationState("captured");
      },
      () => setLocationState("unavailable"),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 30_000 },
    );
  }

  async function submitReport(event) {
    event.preventDefault();
    if (!audio) {
      setError("Please record the emergency report before sending.");
      return;
    }
    setPhase("sending");
    setError("");
    try {
      const result = await createWebIncident({
        audio,
        language: language.code,
        emergencyType: emergencyType || "Other",
        confirmedAddress: address.trim() || "Location not yet confirmed",
        rawTranscript,
        confirmedTranscript,
        durationSeconds: seconds,
        coordinates,
        trainingConsent,
      });
      setIncidentId(result.incident_id);
      setPhase("sent");
    } catch (submitError) {
      setPhase("review");
      setError(submitError.message);
    }
  }

  function startAgain() {
    setPhase("ready");
    setSeconds(0);
    setAudio(null);
    setRawTranscript("");
    setConfirmedTranscript("");
    setEmergencyType("");
    setAddress("");
    setCoordinates(null);
    setLocationState("idle");
    setLocationSuggestion("");
    setIncidentId("");
    setTrainingConsent(false);
    setError("");
  }

  if (phase === "sent") {
    return (
      <main className="callerShell callerShell--centered">
        <section className="sentCard" aria-live="polite">
          <span className="sentCheck" aria-hidden="true">✓</span>
          <p className="callerEyebrow">Report received</p>
          <h1>A dispatcher can now review your report.</h1>
          <p>Keep your phone available. If it is safe, remain near the location you provided.</p>
          <div className="referenceCode"><span>Reference</span><strong>{incidentId}</strong></div>
          <button className="secondaryButton" onClick={startAgain} type="button">Send another report</button>
        </section>
      </main>
    );
  }

  return (
    <main className="callerShell">
      <header className="callerHeader">
        <a className="brandMark" href="/" aria-label="Aabo home">
          <span aria-hidden="true">A</span>
          <div><strong>Aabo</strong><small>Call +234 201 350 2017</small></div>
        </a>
        <a className="dispatchLink" href="/dispatch">Dispatcher console <span aria-hidden="true">↗</span></a>
      </header>

      <section className="voiceStage" aria-labelledby="voice-title">
        <div className="voiceIntro">
          <p className="callerEyebrow">Speak in the language you know best</p>
          <h1 id="voice-title">{phase === "recording" ? "We are listening" : language.prompt}</h1>
          <p>{phase === "recording" ? "Describe the emergency and say the street, area, or nearest landmark." : "Choose a language, then record a short emergency report."}</p>
        </div>

        <div className={`voiceOrbWrap ${isRecording ? "voiceOrbWrap--active" : ""}`}>
          <div className="voicePulse voicePulse--one" />
          <div className="voicePulse voicePulse--two" />
          <button
            className="voiceOrb"
            disabled={phase === "transcribing" || phase === "sending"}
            onClick={isRecording ? finishRecording : beginRecording}
            type="button"
            aria-label={isRecording ? "Stop recording" : "Start recording"}
          >
            <span className="orbGlow" />
            {isRecording ? <span className="stopGlyph" /> : (
              <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 15.4a3.8 3.8 0 0 0 3.8-3.8V6.2a3.8 3.8 0 1 0-7.6 0v5.4a3.8 3.8 0 0 0 3.8 3.8Zm-5.6-3.8a.9.9 0 1 0-1.8 0 7.4 7.4 0 0 0 6.5 7.35V21H8.8a.9.9 0 1 0 0 1.8h6.4a.9.9 0 1 0 0-1.8h-2.3v-2.05a7.4 7.4 0 0 0 6.5-7.35.9.9 0 1 0-1.8 0 5.6 5.6 0 1 1-11.2 0Z" /></svg>
            )}
          </button>
        </div>

        <div className="voiceStatus" role="status">
          {phase === "recording" && <><span className="liveDot" /> Recording · {formatTime(seconds)}</>}
          {phase === "transcribing" && <><span className="loadingDot" /> Understanding your report…</>}
          {phase === "ready" && `Tap the microphone to begin · up to ${MAX_RECORDING_SECONDS} seconds`}
          {phase === "review" && "Recording complete · review before sending"}
          {phase === "sending" && "Sending securely…"}
        </div>

        <div className="languageCarousel" aria-label="Report language">
          {LANGUAGES.map((option) => (
            <button
              className={option.code === language.code ? "languagePill languagePill--active" : "languagePill"}
              disabled={phase !== "ready"}
              key={option.code}
              onClick={() => setLanguage(option)}
              type="button"
            >{option.name}</button>
          ))}
        </div>
        <div className="carouselDots" aria-hidden="true">
          {LANGUAGES.map((option) => <span className={option.code === language.code ? "active" : ""} key={option.code} />)}
        </div>
      </section>

      {error && <div className="callerError" role="alert">{error}</div>}

      {(phase === "review" || phase === "sending") && (
        <form className="reviewSheet" onSubmit={submitReport}>
          <div className="reviewHeading">
            <div><p className="callerEyebrow">Confirm the details</p><h2>Help the dispatcher find you</h2></div>
            {audioUrl && <audio controls preload="metadata" src={audioUrl}>Your browser cannot play this recording.</audio>}
          </div>

          <fieldset className="typeChoices">
            <legend>What kind of emergency is this?</legend>
            <div>{EMERGENCY_TYPES.map((type) => (
              <button className={emergencyType === type ? "typeChoice typeChoice--active" : "typeChoice"} key={type} onClick={() => setEmergencyType(type)} type="button">{type}</button>
            ))}</div>
          </fieldset>

          <label className="fieldLabel" htmlFor="confirmed-transcript">What we heard <span>Correct any wrong words or names</span></label>
          <textarea id="confirmed-transcript" onChange={(event) => setConfirmedTranscript(event.target.value)} rows="4" value={confirmedTranscript} />

          <label className="fieldLabel" htmlFor="confirmed-address">Exact location <span>House number, street, area, and nearest landmark</span></label>
          <input id="confirmed-address" onChange={(event) => setAddress(event.target.value)} placeholder="e.g. No. 19, Osumeyi Street, Awada" value={address} />
          {locationSuggestion && <p className="locationSuggestion">Suggested from the recording — confirm or correct every place name before sending.</p>}

          <button className={`locationButton locationButton--${locationState}`} onClick={requestLocation} type="button">
            <span aria-hidden="true">⌖</span>
            {locationState === "locating" ? "Getting phone location…" : locationState === "captured" ? "Phone location attached" : locationState === "unavailable" ? "Location unavailable — enter address above" : "Attach my phone location"}
          </button>

          <label className="trainingConsent">
            <input checked={trainingConsent} onChange={(event) => setTrainingConsent(event.target.checked)} type="checkbox" />
            <span><strong>Help improve Nigerian-language recognition</strong><small>Allow this recording and your corrected transcript to be reviewed for model improvement. This is optional.</small></span>
          </label>

          <div className="reviewActions">
            <button className="textButton" disabled={phase === "sending"} onClick={startAgain} type="button">Record again</button>
            <button className="submitReport" disabled={phase === "sending"} type="submit">{phase === "sending" ? "Sending…" : "Send to dispatcher"}</button>
          </div>
          <p className="consentNote">Missing details will be flagged for dispatcher follow-up. By sending, you consent to sharing this recording and location with the emergency response team.</p>
        </form>
      )}

      <footer className="callerFooter"><span>Your recording is reviewed by a human dispatcher.</span><span>Powered by N-ATLaS Nigerian language models</span></footer>
    </main>
  );
}
