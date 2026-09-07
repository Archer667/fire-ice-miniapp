import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { GameProvider } from './store.jsx';
import './index.css';
import { api } from './api.js';
import { applyRuntimeGamedata } from './gamedata.js';
import { syncGameClock } from './gameClock.js';

Promise.all([api.gamedata().then(applyRuntimeGamedata), api.gameStatus().then(syncGameClock)]).catch(() => null).finally(() => {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <GameProvider><App /></GameProvider>
  );
});
