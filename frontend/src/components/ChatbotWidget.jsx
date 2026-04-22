import { useEffect, useRef, useState } from 'react';
import { Bot, MessageCircle, Send, X } from 'lucide-react';
import { chatbotService } from '../services/chatbotService';

export default function ChatbotWidget({ token }) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi, I am AuraCare AI Assistant. Ask me anything about residents, schedules, metrics, and facility data.' },
  ]);
  const messageListRef = useRef(null);

  useEffect(() => {
    const node = messageListRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, loading, open]);

  const handleSend = async () => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setMessages((current) => [...current, { role: 'user', text: trimmed }]);
    setQuestion('');
    setLoading(true);
    try {
      const data = await chatbotService.ask(trimmed, token);
      setMessages((current) => [...current, { role: 'assistant', text: data.answer || 'No answer returned.' }]);
    } catch (err) {
      const backendError = err.response?.data?.error;
      const backendDetails = err.response?.data?.details;
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          text: backendDetails ? `${backendError || 'Chatbot error'}: ${backendDetails}` : (backendError || 'Chatbot unavailable right now.'),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const edge = '1.4rem';
  const fabSize = 58;
  const gap = 12;

  return (
    <>
      {open && (
        <div
          style={{
            position: 'fixed',
            right: edge,
            bottom: `calc(${edge} + ${fabSize}px + ${gap}px)`,
            zIndex: 1000,
            width: 'min(420px, calc(100vw - 1.6rem))',
            height: 'min(560px, calc(100vh - 5.5rem))',
            maxHeight: `calc(100vh - ${edge} - ${fabSize}px - ${gap}px - 0.5rem)`,
            backgroundColor: 'white',
            borderRadius: '18px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
            border: '1px solid #D8E4EB',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ padding: '0.9rem 1rem', background: 'linear-gradient(135deg, var(--midnight-green) 0%, #123B57 100%)', color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
              <Bot size={16} /> AuraCare Chat
            </div>
            <button type="button" onClick={() => setOpen(false)} style={{ color: 'white', border: 'none', background: 'transparent' }}>
              <X size={16} />
            </button>
          </div>

          <div
            ref={messageListRef}
            style={{ flex: 1, overflowY: 'auto', padding: '0.8rem', display: 'grid', gap: '0.6rem', backgroundColor: '#F7FBFD', alignContent: 'start' }}
          >
            {messages.map((message, idx) => (
              <div
                key={`${message.role}-${idx}`}
                style={{
                  justifySelf: message.role === 'user' ? 'end' : 'start',
                  maxWidth: '92%',
                  backgroundColor: message.role === 'user' ? 'var(--moonstone)' : 'white',
                  color: message.role === 'user' ? 'white' : 'var(--text-dark)',
                  borderRadius: '12px',
                  padding: '0.6rem 0.75rem',
                  border: message.role === 'assistant' ? '1px solid #E0EAF0' : 'none',
                  fontSize: '0.9rem',
                  lineHeight: 1.45,
                  whiteSpace: 'pre-wrap',
                  overflowWrap: 'anywhere',
                  wordBreak: 'break-word',
                }}
              >
                {message.text}
              </div>
            ))}
            {loading && <div style={{ color: 'var(--text-light)', fontSize: '0.85rem' }}>Thinking...</div>}
          </div>

          <div style={{ borderTop: '1px solid #E4EDF3', padding: '0.7rem', display: 'flex', gap: '0.5rem' }}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') handleSend();
              }}
              placeholder="Ask a question..."
              style={{ flex: 1, minWidth: 0, border: '1px solid #D8E4EB', borderRadius: '10px', padding: '10px 12px', fontSize: '0.9rem' }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={loading}
              style={{ border: 'none', borderRadius: '10px', width: '42px', backgroundColor: 'var(--midnight-green)', color: 'white', display: 'grid', placeItems: 'center' }}
            >
              <Send size={15} />
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        style={{
          position: 'fixed',
          right: edge,
          bottom: edge,
          zIndex: 1001,
          width: `${fabSize}px`,
          height: `${fabSize}px`,
          borderRadius: '999px',
          border: 'none',
          background: 'linear-gradient(135deg, var(--moonstone) 0%, #2f8fa0 100%)',
          color: 'white',
          boxShadow: '0 16px 30px rgba(68,166,181,0.35)',
          display: 'grid',
          placeItems: 'center',
        }}
        title="Open AuraCare chatbot"
      >
        <MessageCircle size={24} />
      </button>
    </>
  );
}
