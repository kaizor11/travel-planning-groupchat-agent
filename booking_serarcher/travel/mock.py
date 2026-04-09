class MockTravelSearchProvider:
    def search_flights(self, structured_data: dict) -> dict:
        return {
            "status": "success",
            "used_params": structured_data,
            "results": [
                {"flight": "Example Airline A", "price": 320},
                {"flight": "Example Airline B", "price": 380},
            ],
        }

    def search_hotels(self, structured_data: dict) -> dict:
        return {
            "status": "success",
            "provider_mode": "mock",
            "used_params": structured_data,
            "results": [
                {"hotel": "Example Hotel A", "price_per_night": 180, "star_rating": 4},
                {"hotel": "Example Hotel B", "price_per_night": 245, "star_rating": 5},
            ],
        }
