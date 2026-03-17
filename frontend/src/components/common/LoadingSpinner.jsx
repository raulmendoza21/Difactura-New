export default function LoadingSpinner({ text = 'Cargando...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
      <div className="w-10 h-10 border-3 border-slate-200 border-t-blue-600 rounded-full animate-spin" />
      <p className="mt-4 text-sm text-slate-400 font-medium">{text}</p>
    </div>
  );
}
