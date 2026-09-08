export default function FamilyIcon({ kind = 'children', s, ...props }) {
  const file = { marriage: 'ring', children: 'crowned-heart', heir: 'stone-throne' }[kind] || 'crowned-heart';
  return <span {...props} aria-hidden="true" className={`family-icon ${props.className || ''}`} style={{...(s ? {width:s,height:s}:{}),...props.style, '--family-icon': `url(/icons/family/${file}.svg)`}} />;
}
