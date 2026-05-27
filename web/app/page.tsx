import Chat from "@/components/Chat";
import HealthBadge from "@/components/HealthBadge";

export default function HomePage() {
  return (
    <main className="flex h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <h1 className="text-base font-semibold tracking-tight">
            SEC 10-K Chat
          </h1>
          <HealthBadge />
        </div>
      </header>
      <Chat />
    </main>
  );
}
