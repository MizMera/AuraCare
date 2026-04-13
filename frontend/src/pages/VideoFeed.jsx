import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Activity, UtensilsCrossed } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function VideoFeed() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [personCount, setPersonCount] = useState(0);
  const [activeMeals, setActiveMeals] = useState([]);
  const [allMeals, setAllMeals] = useState([]);
  const imgRef = useRef(null);

  // Récupérer tous les repas
  const fetchMeals = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/meals/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      setAllMeals(data);
      
      // Déterminer les repas actifs
      const now = new Date();
      const currentMinutes = now.getHours() * 60 + now.getMinutes();
      
      const active = data.filter(meal => {
        const [hours, minutes] = meal.time.split(':');
        const mealMinutes = parseInt(hours) * 60 + parseInt(minutes);
        const diff = currentMinutes - mealMinutes;
        // Actif dans les 30 minutes après l'heure
        return diff >= 0 && diff <= 1;
      });
      
      setActiveMeals(active);
    } catch (err) {
      console.error('Failed to fetch meals', err);
    }
  };
const fetchPersonCount = async () => {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/person-count/', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
    });
    const data = await response.json();
    setPersonCount(data.count);
  } catch (err) {
    console.error('Failed to fetch person count', err);
  }
};
  // Récupérer les notifications pour le compteur
  const fetchNotifications = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/notifications/?unread=true', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      
      // Essayer d'extraire le nombre de personnes de la dernière notification d'absence
      const absenceNotif = data.find(n => n.notification_type === 'ABSENCE');
      if (absenceNotif) {
        const match = absenceNotif.message.match(/Détecté: (\d+)\/(\d+)/);
        if (match) {
          setPersonCount(parseInt(match[1]));
        }
      }
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    }
  };

  useEffect(() => {
    fetchMeals();
    fetchNotifications();
    fetchPersonCount();
    // Polling toutes les 5 secondes
    const interval = setInterval(() => {
      fetchMeals();
      fetchNotifications();
      fetchPersonCount();
    }, 2000);
    
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Connecter au stream vidéo
    const img = imgRef.current;
    if (img) {
      img.src = 'http://127.0.0.1:8000/api/video/stream/';
      img.onload = () => setIsStreaming(true);
      img.onerror = () => setIsStreaming(false);
    }
  }, []);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--alice-blue)' }}>
      <div style={{ padding: '2rem' }}>
        <Link to="/dashboard" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--midnight-green)', textDecoration: 'none', marginBottom: '2rem' }}>
          <ArrowLeft size={20} /> Back to Dashboard
        </Link>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
          {/* Vidéo */}
          <div style={{ backgroundColor: 'white', borderRadius: 'var(--border-radius)', padding: '1rem', boxShadow: 'var(--box-shadow)' }}>
            <h2 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Live Camera Feed</h2>
            <div style={{ position: 'relative' }}>
              <img 
                ref={imgRef}
                alt="Video Stream"
                style={{ width: '100%', borderRadius: 'var(--border-radius-sm)', backgroundColor: '#000', minHeight: '400px' }}
                onError={() => setIsStreaming(false)}
              />
              {!isStreaming && (
                <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center', color: 'white' }}>
                  <Activity size={48} />
                  <p>Connecting to camera...</p>
                </div>
              )}
            </div>
          </div>

          {/* Statistiques */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ backgroundColor: 'white', borderRadius: 'var(--border-radius)', padding: '1.5rem', boxShadow: 'var(--box-shadow)' }}>
              <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1rem' }}>Current Detection</h3>
              <div style={{ fontSize: '3rem', fontWeight: 'bold', color: 'var(--moonstone)' }}>
                {personCount}
              </div>
              <p style={{ color: 'var(--text-light)' }}>People detected</p>
            </div>

            <div style={{ backgroundColor: 'white', borderRadius: 'var(--border-radius)', padding: '1.5rem', boxShadow: 'var(--box-shadow)' }}>
              <h3 style={{ color: 'var(--midnight-green)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <UtensilsCrossed size={18} /> Active Meal Times
              </h3>
              {activeMeals.length > 0 ? (
                activeMeals.map(meal => (
                  <div key={meal.id} style={{ padding: '0.75rem', backgroundColor: '#E0F2FE', borderRadius: '8px', marginBottom: '0.5rem' }}>
                    <strong>{meal.name}</strong>
                    <p style={{ margin: 0, fontSize: '0.85rem' }}>
                      Time: {meal.time} | Expected: {meal.expected_people} people
                    </p>
                  </div>
                ))
              ) : (
                <p style={{ color: 'var(--text-light)' }}>No active meals at this moment</p>
              )}
              
              <h4 style={{ marginTop: '1rem', color: 'var(--midnight-green)' }}>All Meals</h4>
              {allMeals.map(meal => (
                <div key={meal.id} style={{ padding: '0.5rem', borderBottom: '1px solid #eee' }}>
                  <span>{meal.name}</span>
                  <span style={{ float: 'right', color: 'var(--text-light)' }}>{meal.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}