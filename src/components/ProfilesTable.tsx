import * as api from "../lib/api";

export default function ProfilesTable({ data, loading, onAction }: any) {
  if (loading) return <div className="p-8 text-white/70">Загрузка…</div>;
  
  return (
    <div className="overflow-hidden rounded-2xl">
      <table className="w-full text-sm">
        <thead className="text-white/70">
          <tr className="[&>th]:py-3 [&>th]:px-3">
            <th>Название</th>
            <th>Статус</th>
            <th>Язык</th>
            <th>Прокси</th>
            <th>Создан</th>
            <th></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {data.map((p: any, i: number) => (
            <tr key={p.id} className="hover:bg-white/5">
              <td className="py-3 px-3">{p.name || "Профиль"}</td>
              <td className="px-3">
                <span className={`px-2 py-1 rounded-full text-xs ${
                  p.active ? "bg-emerald-500/30" : "bg-white/10"
                }`}>
                  {p.active ? "Активен" : "Неактивен"}
                </span>
              </td>
              <td className="px-3">{p.language || "ru-RU"}</td>
              <td className="px-3">{p.proxy || "—"}</td>
              <td className="px-3">{p.created || "—"}</td>
              <td className="px-3 text-right">
                <button 
                  className="glass rounded-xl px-3 py-1 mr-2 hover:bg-white/14 transition-all" 
                  onClick={() => api.startProfile(p.id).then(onAction)}
                >
                  🚀
                </button>
                <button 
                  className="glass rounded-xl px-3 py-1 hover:bg-white/14 transition-all" 
                  onClick={() => api.selfTest(p.id).then(onAction)}
                >
                  🧪
                </button>
              </td>
            </tr>
          ))}
          {data.length === 0 && (
            <tr>
              <td colSpan={6} className="py-10 text-center text-white/60">
                Пока нет профилей — нажми «Создать»
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
