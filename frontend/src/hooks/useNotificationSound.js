import { useCallback, useEffect, useRef, useState } from 'react';

const STORAGE_KEY = 'auracare.notifications.sound-enabled';

export const useNotificationSound = () => {
  const audioContextRef = useRef(null);
  const [isEnabled, setIsEnabled] = useState(() => {
    if (typeof window === 'undefined') return true;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved !== 'false';
  });

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    window.localStorage.setItem(STORAGE_KEY, isEnabled ? 'true' : 'false');
    return undefined;
  }, [isEnabled]);

  const ensureContext = useCallback(() => {
    if (typeof window === 'undefined') return null;
    if (!audioContextRef.current) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return null;
      audioContextRef.current = new AudioContextClass();
    }
    return audioContextRef.current;
  }, []);

  const playSound = useCallback(async () => {
    if (!isEnabled) return;
    const context = ensureContext();
    if (!context) return;

    if (context.state === 'suspended') {
      try {
        await context.resume();
      } catch {
        return;
      }
    }

    const now = context.currentTime;
    
    // Premier bip (aigu - 880 Hz)
    const osc1 = context.createOscillator();
    const gain1 = context.createGain();
    osc1.type = 'sine';
    osc1.frequency.value = 880;
    gain1.gain.setValueAtTime(0, now);
    gain1.gain.linearRampToValueAtTime(0.12, now + 0.01);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
    osc1.connect(gain1);
    gain1.connect(context.destination);
    osc1.start();
    osc1.stop(now + 0.15);

    // Deuxième bip (plus grave - 660 Hz)
    const osc2 = context.createOscillator();
    const gain2 = context.createGain();
    osc2.type = 'sine';
    osc2.frequency.value = 660;
    gain2.gain.setValueAtTime(0, now + 0.2);
    gain2.gain.linearRampToValueAtTime(0.12, now + 0.21);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc2.connect(gain2);
    gain2.connect(context.destination);
    osc2.start(now + 0.2);
    osc2.stop(now + 0.35);

  }, [ensureContext, isEnabled]);

  const toggleSound = useCallback(() => {
    setIsEnabled((current) => !current);
  }, []);

  return { playSound, toggleSound, isEnabled };
};