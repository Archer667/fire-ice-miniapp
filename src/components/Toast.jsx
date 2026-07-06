import { useGame } from '../store.jsx';

export default function Toast() {
  const { toastMsg, toastVisible } = useGame();
  return <div className={`toast ${toastVisible ? 'show' : ''}`}>{toastMsg}</div>;
}
