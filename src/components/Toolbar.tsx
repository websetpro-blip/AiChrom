import * as api from "../lib/api";

export default function Toolbar({ onReload }: { onReload: () => void }) {
  return (
    <div className="mt-4 flex gap-3 flex-wrap">
      <button 
        onClick={() => api.createProfile().then(onReload)}
        className="glass rounded-2xl px-4 py-2 hover:bg-white/14 transition-all"
      >
        ➕ Создать
      </button>
      <button 
        onClick={() => api.selfTestSelected().then(onReload)}
        className="glass rounded-2xl px-4 py-2 hover:bg-white/14 transition-all"
      >
        🧪 Self-Test
      </button>
      <button 
        onClick={() => api.startSelected().then(onReload)}
        className="glass rounded-2xl px-4 py-2 hover:bg-white/14 transition-all"
      >
        🚀 Запустить
      </button>
      <div className="mx-2 grow" />
      <button 
        onClick={onReload} 
        className="glass rounded-2xl px-4 py-2 hover:bg-white/14 transition-all"
      >
        ↻ Обновить
      </button>
    </div>
  );
}
