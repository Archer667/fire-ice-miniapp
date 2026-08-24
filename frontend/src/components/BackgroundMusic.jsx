import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

const MUTED_KEY = 'valeria-background-music-muted';

export default function BackgroundMusic() {
  const audioRef = useRef(null);
  const [settings, setSettings] = useState(null);
  const [muted, setMuted] = useState(() => localStorage.getItem(MUTED_KEY) === '1');
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    api.musicSettings().then(setSettings).catch(() => setSettings(null));
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !settings?.enabled || !settings.audio_url) return;
    audio.volume = Math.max(0, Math.min(1, Number(settings.volume || 0) / 100));
    audio.loop = settings.loop !== false;
    if (settings.autoplay && !muted) {
      audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  }, [settings, muted]);

  if (!settings?.enabled || !settings.audio_url) return null;

  const toggle = async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause(); setPlaying(false); setMuted(true); localStorage.setItem(MUTED_KEY, '1');
    } else {
      try {
        await audio.play(); setPlaying(true); setMuted(false); localStorage.removeItem(MUTED_KEY);
      } catch (_) { setPlaying(false); }
    }
  };

  return (
    <>
      <audio ref={audioRef} src={settings.audio_url} preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
      <button type="button" className={`music-toggle ${playing ? 'playing' : ''}`} onClick={toggle}
              aria-label={playing ? 'قطع موسیقی پس‌زمینه' : 'پخش موسیقی پس‌زمینه'} title={settings.title}>
        <span>{playing ? '♫' : '♪'}</span>
      </button>
    </>
  );
}

