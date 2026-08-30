import { useEffect } from 'react';
import { haptic } from '../telegram.js';

export default function ProfileImageModal({ image, name, onClose }) {
  useEffect(() => {
    if (!image) return undefined;
    const previousOverflow = document.body.style.overflow;
    const onKeyDown = event => {
      if (event.key === 'Escape') onClose();
    };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [image, onClose]);

  if (!image) return null;

  const close = () => {
    haptic();
    onClose();
  };

  return (
    <div className="profile-image-backdrop" role="dialog" aria-modal="true"
         aria-label={`تصویر پروفایل ${name}`} onClick={close}>
      <div className="profile-image-modal" onClick={event => event.stopPropagation()}>
        <button type="button" className="profile-image-close" onClick={close}
                aria-label="بستن تصویر پروفایل">×</button>
        <img src={image} alt={`تصویر پروفایل ${name}`} />
        <div className="profile-image-name">{name}</div>
      </div>
    </div>
  );
}
