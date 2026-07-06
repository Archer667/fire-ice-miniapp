import { useGame } from '../store.jsx';
export default function Toast() {
  const { toastMsg, show } = useGame();
  return <div className={`toast ${show ? 'show' : ''}`}>{toastMsg}</div>;
}
