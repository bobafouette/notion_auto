import logging
import os
import requests
import sys

from datetime import datetime

URL = "https://api.notion.com/v1"
TRACKER_DATABASE_ID = "ede9aae33f09428aa1a582cd08dddc55"

# Header template to query notion
HEADERS = {
    "Accept": "application/json",
    "Authorization": "Bearer {}",
    "Notion-Version": "2022-02-22",
    "Content-Type": "application/json"
}

# Payload template to create a page into a database
CREATE_PAGE_PAYLOAD = {
    "parent": {
        "type": "database_id",
        "database_id": "{}"
    },
    "properties": {
        "title": {
            "title": [
                {
                    "type": "text",
                    "text": {
                        "content": "{}"
                    }
                }
            ]
        }
    }
}

# Payload template to query a page into a database without any filter
SEARCH_PAGE_PAYLOAD = {
    "filter": {
        "or": []
    }
}



class TooManyDailyTrackingPagse(Exception):

    def __init__(self, nb_tracking_pages):
        self.message = "1 or None daily tracking pages should exists, found {}.".format(nb_tracking_pages)
        super(TooManyDailyTrackingPagse, self).__init__(self.message)



class NotionRequestException(Exception):

    def __init__(self, context_message, http_error):
        self.message = "{}: {}".format(context_message, str(http_error))
        super(NotionRequestException, self).__init__(self.message)


class NoAPIKeyException(Exception):

    def __init__(self) -> None:
        super(NoAPIKeyException, self).__init__("Could not find Notion API Key")


class Singleton(type):

    _instances = {}
    def __call__(cls, *args, **kwds):
        if cls not in cls._instances:
            instance = super(Singleton, cls).__call__(*args, **kwds)
            cls._instances[cls] = instance
        return cls._instances[cls]



class Notion(metaclass=Singleton):


    def __init__(self):
        self.__api_key = get_api_key()
        self.__headers = HEADERS
        self.__headers["Authorization"] = HEADERS.get('Authorization').format(self.__api_key)


    def query_database(self, database_id, filter=None):
        search_database_url = "{}/databases/{}/query".format(URL,database_id)
        search_database_payload = SEARCH_PAGE_PAYLOAD
        if filter:
            search_database_payload["filter"] = filter

        response = requests.post(search_database_url,json=search_database_payload, headers=self.__headers)
        response.raise_for_status()
        return response


    def create_page(self, database_id, title):
        create_page_url = "{}/pages/".format(URL)
        create_page_payload = CREATE_PAGE_PAYLOAD
        create_page_payload["parent"]["database_id"] = database_id
        create_page_payload["properties"]["title"]["title"][0]["text"]["content"] = title

        response = requests.post(create_page_url,json=create_page_payload, headers=self.__headers)
        response.raise_for_status()
        return response



def get_api_key():
    if os.environ.get('NOTION_API_KEY'):
        return os.environ.get('NOTION_API_KEY')
    if os.environ.get('NOTION_API_KEY_PATH') and os.path.isfile(os.environ.get('NOTION_API_KEY_PATH')):
        with open(os.environ.get('NOTION_API_KEY_PATH'), 'r') as api_key_file:
            api_key = api_key_file.read()
        return api_key
    if os.path.isfile(os.path.join(os.path.curdir, '.notion_api_key')):
        with open(os.path.join(os.path.curdir, '.notion_api_key'), 'r') as api_key_file:
            api_key = api_key_file.read()
        return api_key
    raise NoAPIKeyException



def get_daily_tracker_pages():
    daily_title_filter = {
        "or": [
            {
                "property": "Title",
                "title": {
                    "contains": datetime.now().strftime("%a %d %b")
                }
            }
        ]
    }

    notion_api = Notion()
    try:
        response = notion_api.query_database(TRACKER_DATABASE_ID, filter=daily_title_filter)
    except requests.HTTPError as http_error:
        context = "Could not query existing daily tracking pages"
        raise NotionRequestException(context, http_error)

    logging.getLogger('HabitTracker').debug('Fetched existing daily tracking pages')
    return response.json().get('results', [])



def create_daily_tracker_page():
    daily_tacker_pages = get_daily_tracker_pages()
    if len(daily_tacker_pages) == 1:
        logging.getLogger('HabitTracker').warning("A daily tracking page already exists")
        return
    if len(daily_tacker_pages) > 1:
        raise TooManyDailyTrackingPagse(len(daily_tacker_pages))

    notion_api = Notion()
    try:
        notion_api.create_page(TRACKER_DATABASE_ID, datetime.now().strftime("%a %d %b"))
    except requests.HTTPError as http_error:
        context = "Could not create daily tracking page"
        raise NotionRequestException(context, http_error)

    logging.getLogger('HabitTracker').info('Created a new daily tracking page')



if __name__ == "__main__":
    logging.getLogger('HabitTracker').setLevel(logging.INFO)
    sh = logging.StreamHandler(sys.stdout)
    fh = logging.FileHandler('/var/log/notion_auto.log')
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s]: %(message)s')
    sh.setFormatter(formatter)
    fh.setFormatter(formatter)
    logging.getLogger('HabitTracker').addHandler(sh)

    create_daily_tracker_page()