export default function GlassCard({ children, className = "" }: any) {
  return (
    <div className={`glass rounded-3xl p-4 ${className}`}>
      {children}
    </div>
  );
}
