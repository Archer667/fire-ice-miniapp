import { useState, useEffect, useRef } from 'react';
import { useGame } from '../store.jsx';
import { fetchMessages } from '../api.js';
import { haptic } from '../telegram.js';

export default function Chat() {
  const { player } = useGame();
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState('');
  const endRef = useRef(null);

  useEffect(() => { fetchMessages().then(setMsgs); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  const send = () => {
    const t = text.trim();
    if (!t) return;
    haptic();
    setMsgs(prev => [...prev, { who: `${player.house.sigil} تو`, text: t, me: true }]);
    setText('');
  };

  return (
    <>
      <div className="chat-head">
        🐦‍⬛ کلاغ‌های وستروس
        <span>۹۸ لرد آنلاین</span>
      </div>
      <div className="msgs">
        {msgs.map((m, i) => (
          <div key={i} className={`m ${m.me ? 'me' : 'them'}`}>
            <div className="who">{m.who}</div>
            <div className="bub">{m.text}</div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="chat-in">
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="کلاغی بفرست..."
        />
        <button className="send" onClick={send}>📨</button>
      </div>
    </>
  );
}
