import { redirect } from "next/navigation";

// Temporary: redirect to dev test trip until Week 2 adds auth + trip creation
export default function Home() {
  redirect("/trips/test-trip-123");
}
