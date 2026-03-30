import { MessageList } from "@/components/chat/MessageList";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChevronLeft, Video, Phone } from "lucide-react";

// Temporary hardcoded user until Week 2 auth is added
const TEMP_USER_ID = "dev-user-1";

interface TripPageProps {
  params: Promise<{ tripId: string }>;
}

export default async function TripPage({ params }: TripPageProps) {
  const { tripId } = await params;

  return (
    <div className="im-shell">
      {/* iOS-style header */}
      <header className="im-header">
        {/* Status bar spacer (mobile) */}
        <div style={{ height: "env(safe-area-inset-top, 0px)" }} />

        <div className="flex items-center px-2 py-1.5 gap-1">
          {/* Back */}
          <button className="flex items-center text-[#007AFF] gap-0.5 px-1 py-1 rounded-lg active:opacity-50 transition-opacity min-w-[44px]">
            <ChevronLeft size={22} strokeWidth={2.5} />
            <span className="text-[16px]" style={{ fontFamily: "inherit" }}>Back</span>
          </button>

          {/* Center: avatar + name */}
          <div className="flex-1 flex flex-col items-center gap-0.5">
            {/* Avatar stack */}
            <div className="relative flex items-center justify-center">
              <div
                className="w-[42px] h-[42px] rounded-full flex items-center justify-center text-white text-lg font-semibold shadow-sm"
                style={{ background: "linear-gradient(135deg, #5856D6, #007AFF)" }}
              >
                ✈️
              </div>
              {/* Online dot */}
              <span
                className="absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white"
                style={{ background: "#34C759" }}
              />
            </div>
            <div className="flex flex-col items-center leading-tight">
              <span className="text-[13px] font-semibold tracking-tight text-black">TripMind</span>
              <span className="text-[11px]" style={{ color: "#8E8E93" }}>
                Group · {tripId}
              </span>
            </div>
          </div>

          {/* Right icons */}
          <div className="flex items-center gap-3 min-w-[44px] justify-end pr-1">
            <button className="active:opacity-50 transition-opacity" style={{ color: "#007AFF" }}>
              <Video size={22} />
            </button>
            <button className="active:opacity-50 transition-opacity" style={{ color: "#007AFF" }}>
              <Phone size={20} />
            </button>
          </div>
        </div>
      </header>

      <MessageList tripId={tripId} currentUserId={TEMP_USER_ID} />
      <ChatInput tripId={tripId} currentUserId={TEMP_USER_ID} />
    </div>
  );
}
