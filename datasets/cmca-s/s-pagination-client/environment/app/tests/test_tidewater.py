import json
import unittest

from freight.tidewater import Response, list_all


class ListAllTest(unittest.TestCase):
    def test_single_page(self):
        sent = []

        def transport(path, params):
            sent.append((path, dict(params)))
            body = {"data": [{"id": "shp_1"}, {"id": "shp_2"}], "has_more": False, "next_cursor": "c9f2"}
            return Response(200, {"Content-Type": "application/json"}, json.dumps(body).encode())

        items = list_all(transport, "shipments", sleep=lambda s: None)
        self.assertEqual([i["id"] for i in items], ["shp_1", "shp_2"])
        self.assertEqual(sent[0][0], "/v2/shipments")


if __name__ == "__main__":
    unittest.main()
