import { useState } from 'react';

export default function PlayerFlag({ src, name = '', className = '' }) {
  const [failed, setFailed] = useState(null);
  if (!src || failed === src) return null;
  return <span className={`player-flag ${className}`}>
    <img src={src} alt={name ? `پرچم ${name}` : 'پرچم بازیکن'}
      loading="lazy" decoding="async" onError={() => setFailed(src)} />
  </span>;
}
