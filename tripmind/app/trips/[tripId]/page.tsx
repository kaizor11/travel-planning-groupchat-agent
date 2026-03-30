import { MessageList } from "@/components/chat/MessageList";
import { ChatInput } from "@/components/chat/ChatInput";

// Temporary hardcoded user until Week 2 auth is added
const TEMP_USER_ID = "dev-user-1";

interface TripPageProps {
  params: Promise<{ tripId: string }>;
}

export default async function TripPage({ params }: TripPageProps) {
  const { tripId } = await params;

  return (
    <main className="flex flex-col h-screen bg-background">
      <header className="border-b border-border px-4 py-3 flex items-center gap-2">
        <h1 className="font-semibold text-sm">TripMind</h1>
        <span className="text-xs text-muted-foreground">· {tripId}</span>
      </header>

      <MessageList tripId={tripId} currentUserId={TEMP_USER_ID} />
      <ChatInput tripId={tripId} currentUserId={TEMP_USER_ID} />
    </main>
  );
}
