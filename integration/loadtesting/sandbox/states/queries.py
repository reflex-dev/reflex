import uuid
import httpx
from sandbox.states.base import BaseState


# test URL: str = https://jsonplaceholder.typicode.com/posts
# test URL: str = https://jsonplaceholder.typicode.com/todos


class QueryState(BaseState):

    # vars for handling request calls ...
    req_methods: list[str] = ["GET", "POST"]
    req_url: str = "https://jsonplaceholder.typicode.com/posts"
    current_req: str = "GET"
    get_params_body: list[str] = ["JSON", "Raw", "None"]
    post_params_body: list[str] = [
        "JSON",
        "Raw",
        "x-www-form-urlencoded",
        "Form Data",
        "Binary",
        "None",
    ]

    # params. for triggering API calls ...
    url_param: dict[str, str]
    headers: list[dict[str, str]]
    body: list[dict[str, str]]
    cookies: list[dict[str, str]]

    # vars for GET request ...
    get_data: list[dict[str, str]]
    get_table_headers: list[str]
    paginated_data: list[dict[str, str]]

    # vars for pagination ...
    number_of_rows: int
    limits: list[str] = ["10", "20", "50"]
    current_limit: int = 10
    offset: int = 0
    current_page: int = 1
    total_pages: int = 1
    formatted_headers: dict

    def get_request(self, method: str):
        self.current_req = method

    def add_header(self):
        self.headers.append(
            {"id": str(uuid.uuid4()), "identifier": "headers", "key": "", "value": ""}
        )

    def add_body(self):
        self.body.append(
            {"id": str(uuid.uuid4()), "identifier": "body", "key": "", "value": ""}
        )

    def add_cookies(self):
        self.cookies.append(
            {"id": str(uuid.uuid4()), "identifier": "cookies", "key": "", "value": ""}
        )

    def pure(self):
        return

    def remove_entry(self, data: dict[str, str]):
        if data["identifier"] == "headers":
            self.headers = [item for item in self.headers if item["id"] != data["id"]]

        if data["identifier"] == "body":
            self.body = [item for item in self.body if item["id"] != data["id"]]

        if data["identifier"] == "cookies":
            self.cookies = [item for item in self.cookies if item["id"] != data["id"]]

    async def update_attribute(self, data: dict[str, str], attribute: str, value: str):
        data[attribute] = value

        if data["identifier"] == "headers":
            self.headers = [
                data if item["id"] == data["id"] else item for item in self.headers
            ]

        if data["identifier"] == "body":
            self.body = [
                data if item["id"] == data["id"] else item for item in self.body
            ]

        if data["identifier"] == "cookies":
            self.cookies = [
                data if item["id"] == data["id"] else item for item in self.cookies
            ]

    async def update_keyy(self, key: str, data: dict[str, str]):
        await self.update_attribute(data, "key", key)

    async def update_value(self, value: str, data: dict[str, str]):
        await self.update_attribute(data, "value", value)


class QueryAPI(QueryState):

    # vars to update row entries ...
    is_open: bool = False
    selected_entry: dict[str, str]
    original_entry: dict[str, str]

    async def process_headers(self):
        for item in self.headers:
            if item["key"]:
                self.formatted_headers[item["key"]] = item["value"]

    async def run_get_request(self):
        await self.process_headers()
        async with httpx.AsyncClient() as client:
            res = await client.get(self.req_url, headers=self.formatted_headers)

            self.get_data = res.json()
            self.number_of_rows = len(self.get_data)
            self.get_table_headers = list(self.get_data[0].keys())

            # Calculate the total number of pages
            self.total_pages = (
                self.number_of_rows + self.current_limit - 1
            ) // self.current_limit

            # Initialize the data to the first page
            self.paginate()

    def paginate(self):
        start = self.offset
        end = start + self.current_limit
        self.paginated_data = self.get_data[start:end]
        self.current_page = (self.offset // self.current_limit) + 1

    def delta_limit(self, limit: str):
        self.current_limit = int(limit)
        self.offset = 0
        self.total_pages = (
            self.number_of_rows + self.current_limit - 1
        ) // self.current_limit
        self.paginate()

    def pure(self):
        return

    def previous(self):
        if self.offset >= self.current_limit:
            self.offset -= self.current_limit
        else:
            self.offset = 0

        self.paginate()

    def next(self):
        if self.offset + self.current_limit < self.number_of_rows:
            self.offset += self.current_limit

        self.paginate()

    def delta_drawer(self):
        self.is_open = not self.is_open

    def display_selected_row(self, data: dict[str, str]):
        self.delta_drawer()
        self.selected_entry = data.copy()
        self.original_entry = data

    def update_data(self, value: str, data: tuple[str, str]):
        self.selected_entry[data[0]] = value

    def commit_changes(self):
        self.get_data = [
            self.selected_entry if item == self.original_entry else item
            for item in self.get_data
        ]

        self.paginate()
        self.delta_drawer()
