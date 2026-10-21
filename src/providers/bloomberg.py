class BloombergProvider:
    """Optional interface only. Requires authorized Desktop API and explicit usage rights."""

    def get_history(self, series_id, start_date, end_date=None):
        raise NotImplementedError("Bloomberg integration requires licensed Desktop API access")

    def get_latest(self, series_id):
        raise NotImplementedError("No Bloomberg session configured")

    def get_metadata(self, series_id):
        return {"status": "UNAVAILABLE", "license": "Bloomberg authorization required"}
