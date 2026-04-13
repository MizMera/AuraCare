// src/hooks/useNotificationSound.js
import { useRef, useEffect, useState } from 'react';

export const useNotificationSound = () => {
  const audioRef = useRef(null);
  const [isEnabled, setIsEnabled] = useState(true);

  useEffect(() => {
    // Créer l'élément audio
    audioRef.current = new Audio('/notification.mp3');
    audioRef.current.volume = 0.5;
    
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const playSound = () => {
    if (isEnabled && audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play().catch(err => console.log('Audio play error:', err));
    }
  };

  const toggleSound = () => setIsEnabled(!isEnabled);

  return { playSound, toggleSound, isEnabled };
};