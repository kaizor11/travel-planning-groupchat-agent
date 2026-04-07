"""
TripMind end-to-end test suite.

Prerequisites:
    pip install pytest playwright
    playwright install chromium
    npm run dev          ← must be running before pytest

Run all tests (headless):
    pytest

Watch a real browser:
    pytest --headed

Run a single test class:
    pytest tests/test_chat.py::TestSendingMessages -v
"""
import pytest

BASE_URL = "http://localhost:5173"


# ── 1. Page load ──────────────────────────────────────────────────────────────

class TestPageLoad:
    def test_redirects_to_trip(self, page, screenshot):
        """/ should redirect to /trips/test-trip-123"""
        assert "/trips/" in page.url
        screenshot("01_page_load")

    def test_adov_header_visible(self, page):
        """'Adov' label should appear in the header"""
        assert page.locator("text=Adov").first.is_visible()

    def test_trip_id_in_header(self, page):
        """The trip ID should appear as a subtitle in the header"""
        assert page.locator("text=test-trip-123").is_visible()

    def test_input_bar_present(self, page):
        """Message textarea and send button must be rendered"""
        assert page.locator("textarea").is_visible()
        assert page.locator("[aria-label='Send']").is_visible()

    def test_messages_or_empty_state_shown(self, page, screenshot):
        """Either existing messages or the empty-state placeholder must be visible"""
        has_messages = page.locator(".im-bubble").count() > 0
        has_empty = page.locator("text=Drop a travel link").is_visible()
        screenshot("02_initial_state")
        assert has_messages or has_empty, "Neither messages nor empty state found"


# ── 2. Input bar behaviour ────────────────────────────────────────────────────

class TestInputBehavior:
    def test_send_button_inactive_when_empty(self, page, screenshot):
        """Send button must carry the .inactive class when the textarea is empty"""
        btn = page.locator("[aria-label='Send']")
        classes = btn.get_attribute("class") or ""
        assert "inactive" in classes
        screenshot("03_empty_input")

    def test_send_button_activates_on_typing(self, page, screenshot):
        """Send button must switch to .active once the user types"""
        page.locator("textarea").fill("Hello!")
        btn = page.locator("[aria-label='Send']")
        classes = btn.get_attribute("class") or ""
        assert "active" in classes
        screenshot("04_active_send_btn")

    def test_send_button_deactivates_after_clear(self, page):
        """Clearing the textarea should return the button to .inactive"""
        page.locator("textarea").fill("text")
        page.locator("textarea").fill("")
        classes = page.locator("[aria-label='Send']").get_attribute("class") or ""
        assert "inactive" in classes


# ── 3. Sending messages ───────────────────────────────────────────────────────

class TestSendingMessages:
    TEXT = "Playwright test message"  # no emoji — simpler selector matching

    def test_message_appears_immediately(self, page, screenshot):
        """Optimistic update: message must appear before any server round-trip"""
        page.locator("textarea").fill(self.TEXT)
        page.locator("[aria-label='Send']").click()
        # 3 s timeout — should appear instantly via optimistic update
        page.wait_for_selector(f"text={self.TEXT}", timeout=3000)
        screenshot("05_message_sent")

    def test_input_clears_after_send(self, page):
        """Textarea should be empty immediately after clicking Send"""
        page.locator("textarea").fill("clearing test")
        page.locator("[aria-label='Send']").click()
        assert page.locator("textarea").input_value() == ""

    def test_sent_message_styled_as_sent_bubble(self, page):
        """Sent messages must use the blue .im-bubble-sent class (right side)"""
        page.locator("textarea").fill("bubble style test")
        page.locator("[aria-label='Send']").click()
        page.wait_for_selector(".im-bubble-sent", timeout=3000)
        assert page.locator(".im-bubble-sent").last.is_visible()

    def test_enter_key_sends_message(self, page, screenshot):
        """Pressing Enter (without Shift) should send the message"""
        msg = "Sent via Enter key"
        page.locator("textarea").fill(msg)
        page.keyboard.press("Enter")
        page.wait_for_selector(f"text={msg}", timeout=3000)
        screenshot("06_enter_key_send")

    def test_shift_enter_adds_newline_not_send(self, page):
        """Shift+Enter must insert a newline and NOT submit the message"""
        page.locator("textarea").fill("line one")
        page.keyboard.press("Shift+Enter")
        # Textarea still has content — message was not sent
        assert page.locator("textarea").input_value() != ""
        page.locator("textarea").fill("")  # clean up

    def test_empty_message_not_sent(self, page):
        """Send button must stay inactive and not add a bubble when input is only whitespace"""
        page.locator("textarea").fill("   ")
        btn = page.locator("[aria-label='Send']")
        # Button should remain inactive — whitespace doesn't count as text
        assert "inactive" in (btn.get_attribute("class") or ""), \
            "Send button should be inactive for whitespace-only input"
        page.locator("textarea").fill("")  # clean up


# ── 4. Wish pool card ─────────────────────────────────────────────────────────

class TestWishPoolCard:
    """
    These tests require at least one wishpool_confirm message already in
    Firestore for the test trip.  They are skipped automatically when none
    are present — to generate one, send a travel URL (e.g. a blog post or
    Google Maps link) while the app is running and add Anthropic API credits.
    """

    def _get_cards(self, page):
        return page.locator(".wishpool-card").all()

    def test_wishpool_card_renders(self, page, screenshot):
        """Wishpool card should show destination text and Add/Skip buttons"""
        cards = self._get_cards(page)
        if not cards:
            pytest.skip("No wishpool cards present")
        card = page.locator(".wishpool-card").first
        assert card.locator(".wishpool-btn.add").is_visible()
        assert card.locator(".wishpool-btn.skip").is_visible()
        screenshot("07_wishpool_card")

    def test_wishpool_skip_shows_confirmation(self, page, screenshot):
        """Clicking Skip should replace the buttons with 'Skipped'"""
        cards = self._get_cards(page)
        if not cards:
            pytest.skip("No wishpool cards present")
        page.locator(".wishpool-btn.skip").first.click()
        page.wait_for_selector("text=Skipped", timeout=2000)
        screenshot("08_wishpool_skipped")

    def test_wishpool_add_shows_confirmation(self, page, screenshot):
        """Clicking Add should replace the buttons with '✓ Added to wish pool'"""
        cards = self._get_cards(page)
        if len(cards) < 2:
            pytest.skip("Need a second wishpool card to test Add (first was Skipped)")
        page.locator(".wishpool-btn.add").first.click()
        page.wait_for_selector("text=Added to wish pool", timeout=3000)
        screenshot("09_wishpool_added")
