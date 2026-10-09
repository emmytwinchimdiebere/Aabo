import { useCallback, useRef, useState } from "react";

const OUTPUT_SAMPLE_RATE = 16_000;
const SILENCE_FRAME_SECONDS = 0.02;
const SILENCE_PADDING_SECONDS = 0.2;

function mergeBuffers(buffers) {
  const length = buffers.reduce((total, buffer) => total + buffer.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  for (const buffer of buffers) {
    merged.set(buffer, offset);
    offset += buffer.length;
  }
  return merged;
}

function downsample(samples, inputRate) {
  if (inputRate === OUTPUT_SAMPLE_RATE) return samples;
  const ratio = inputRate / OUTPUT_SAMPLE_RATE;
  const output = new Float32Array(Math.floor(samples.length / ratio));
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(Math.floor((index + 1) * ratio), samples.length);
    let sum = 0;
    for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
      sum += samples[sampleIndex];
    }
    output[index] = sum / Math.max(1, end - start);
  }
  return output;
}

function trimSilence(samples) {
  const frameSize = Math.max(1, Math.round(OUTPUT_SAMPLE_RATE * SILENCE_FRAME_SECONDS));
  const frameCount = Math.floor(samples.length / frameSize);
  if (frameCount < 2) return samples;

  const levels = [];
  for (let frameIndex = 0; frameIndex < frameCount; frameIndex += 1) {
    let energy = 0;
    const offset = frameIndex * frameSize;
    for (let index = 0; index < frameSize; index += 1) {
      const sample = samples[offset + index];
      energy += sample * sample;
    }
    levels.push(Math.sqrt(energy / frameSize));
  }

  const peakLevel = Math.max(...levels);
  if (peakLevel < 0.002) return samples;
  const threshold = Math.max(0.004, peakLevel * 0.08);
  const firstActive = levels.findIndex((level) => level >= threshold);
  let lastActive = -1;
  for (let index = levels.length - 1; index >= 0; index -= 1) {
    if (levels[index] >= threshold) {
      lastActive = index;
      break;
    }
  }
  if (firstActive < 0 || lastActive < firstActive) return samples;

  const padding = Math.round(OUTPUT_SAMPLE_RATE * SILENCE_PADDING_SECONDS);
  const start = Math.max(0, firstActive * frameSize - padding);
  const end = Math.min(samples.length, (lastActive + 1) * frameSize + padding);
  return samples.slice(start, end);
}

function encodeWav(samples) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeText = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };

  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, OUTPUT_SAMPLE_RATE, true);
  view.setUint32(28, OUTPUT_SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * 2, true);

  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

export function useWavRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const sessionRef = useRef(null);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone recording is not supported in this browser.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const context = new AudioContext();
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const buffers = [];
    processor.onaudioprocess = (event) => {
      buffers.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    source.connect(processor);
    processor.connect(context.destination);
    sessionRef.current = { buffers, context, processor, source, stream };
    setIsRecording(true);
  }, []);

  const stop = useCallback(async () => {
    const session = sessionRef.current;
    if (!session) throw new Error("No recording is in progress.");
    session.processor.disconnect();
    session.source.disconnect();
    session.stream.getTracks().forEach((track) => track.stop());
    const inputRate = session.context.sampleRate;
    await session.context.close();
    sessionRef.current = null;
    setIsRecording(false);
    const samples = downsample(mergeBuffers(session.buffers), inputRate);
    return encodeWav(trimSilence(samples));
  }, []);

  return { isRecording, start, stop };
}
