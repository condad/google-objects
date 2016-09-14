"""

Google Slides Models
    Tue 13 Sep 22:16:41 2016

"""
import re
import importlib
from google_sliders.utils import UpdateReq


# TODO:
#     i/ ensure replace_text always recieves a real value
#     ii/ ensure all cell data reflects table row insertion
#     and deletion

"""Presentation"""


class Presentation(object):
    """Google Presentation Object,
    holds batch update request lists and
    passes it to its <Client> for execution.

    """
    def __init__(self, client, presentation):
        """Class for Presentation object

        :client: <Client> from .client

        """
        self._client = client
        self._updates = []

        # load presentation metadata

        self._id = presentation.get('presentationId')
        self._title = presentation.get('title')
        self._locale = presentation.get('local')
        self._width = presentation.get('pageSize').get('width')
        self._length = presentation.get('pageSize').get('length')

        # load page objects
        self._pages = [Page(self, page) for page in presentation.get('slides')]
        self._masters = [Page(self, page) for page in presentation.get('masters')]
        self._layouts = [Page(self, page) for page in presentation.get('layouts')]

    def __iter__(self):
        for page in self._pages:
            yield page

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.update()
        return True

    def update(self):
        self._client.push_updates(self._id, self._updates)

        # TODO: add success handlers
        del self._updates[:]

    def add_update(self, update):
        """Adds update of type <Dict>
        to updates list

        :update: <Dict> of update request
        :returns: <Bool> of if request was added

        """
        if type(update) is dict:
            self._updates.append(update)
            return True
        else:
            return False

    def find_tags(self, regex):
        """Search all Presentation text
        for matches with regex, returning
        the list of unique matches.

        :regex: a raw regex <String>
        :returns: <List> of matches

        """
        tags = set()
        for page in self._pages:
            for element in page:
                if type(element) is Shape:
                    tags.add(element.seek(regex))
                if type(element) is Table:
                    matches = element.seek(regex)
                    for match in matches:
                        tags.add(match)
        return tags

    def replace_text(self, find, replace, case_sensitive=False):
        """Add update request for presentation-wide
        replacement with arg:find to arg:replace
        """

        if not find:
            return
        self.add_update(
            UpdateReq.replace_all_text(find, replace, case_sensitive)
        )

    def __getattr__(self, name):
        """Handle sub-class instantiation.

            :name (str): Name of model to instantiate.

        Returns: Instance of named class.
        """
        try:
            # api class first
            model = getattr(importlib.import_module(
                __package__ + '.' + name.lower()), name)

            self._log.debug('loaded instance of api class %s', name)
            return model(self)
        except ImportError:
            try:
                model = getattr(importlib.import_module(
                    name.lower()), name)
                self._log.debug('loaded instance of model class %s', name)
                return model()
            except ImportError:
                self._log.debug('ImportError! Cound not load api or model class %s', name)
                return name



"""Page"""


class Page(object):
    """Docstring for Page. """

    def __init__(self, presentation, page):
        self._presentation = presentation

        # load metadata
        self._id = page.get('objectId')
        self._type = page.get('pageType')
        self._elements = []

        # load elements
        for element in page.get('pageElements'):
            self._elements.append(self._load_element(element))

    def __iter__(self):
        for element in self._elements:
            yield element

    def _load_element(self, element):
        """Initialize element object from
        from slide element dict

        :elements: <Dict>
        :returns: NONE

        """
        if 'shape' in element:
            obj = Shape(self, **element)
            self._elements.append(obj)
        elif 'table' in element:
            obj = Table(self, **element)
            self._elements.append(obj)
        elif 'image' in element:
            pass
        elif 'video' in element:
            pass
        elif 'wordArt' in element:
            pass
        elif 'sheetsChart' in element:
            pass
        elif 'elementGroup' in element:
            for child in element.get('children'):
                self._load_element(child)
            return

        # self._elements.append(obj)

    def add_update(self, update):
        """Adds update of type <Dict>
        to updates list
        """
        return self._presentation.add_update(update)



"""Base Page Element"""


class PageElement(object):
    """Initialized PageElement object and
    sets metadata properties and shared object
    operations.
    """

    def __init__(self, page, **kwargs):
        self._page = page

        # initialize metadata
        self._id = kwargs.pop('objectId')
        self._size = kwargs.pop('size')
        self._transform = kwargs.pop('transform')
        # self._title = kwargs.pop('title')
        # self._description = kwargs.pop('description')

    def update(self, update):
        return self._page.add_update(update)

    def delete(self):
        """Adds deleteObject request to
        presentation updates list.
        """
        self._page.add_update(
            UpdateReq.delete_object(self._id)
        )



"""Sub Elements"""


class Shape(PageElement):
    """Docstring for Shape. """

    def __init__(self, page, **kwargs):
        """Shape Element from Slides"""
        shape = kwargs.pop('shape')
        super(self.__class__, self).__init__(page, **kwargs)

        # set metadata
        self._type = shape.get('shapeType')

        # set text values
        if shape.get('text'):
            self._text = shape.get('text').get('rawText')
            self._rendered = shape.get('text').get('renderedText')
        else:
            self._text = None
            self._rendered = None

    def seek(self, regex):
        """Returns Shape text if regular expression
        matches it.

        :regex: Raw <String>
        :returns: self.text OR None

        """
        if not self.text:
            return
        if re.match(regex, self.text):
            return self.text
        return

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        if not self._text:
            # TODO: apply deleteText
            self.update(
                UpdateReq.delete_text()
            )
        # TODO: apply insertText
        self.update(
            UpdateReq.insert_text()
        )
        self._text = value

    @text.deleter
    def text(self):
        self.update(
            UpdateReq.delete_text()
        )


class Table(PageElement):
    """Docstring for Table."""

    # TODO:
    #     i/ add dynamic row functionality
    #     that works in tandem with corresponding cells

    class Cell(object):
        """Table Cell, only used by table"""

        def __init__(self, table, cell):
            self._table = table

            # initialize metadata
            self._row = cell.get('location').get('rowIndex')
            self._column = cell.get('location').get('columnIndex')
            self._row_span = cell.get('rowSpan')
            self._column_span = cell.get('rowColumn')

            # initialize values
            self._text = cell.get('text').get('rawText')
            self._rendered = cell.get('text').get('renderedText')

        @property
        def text(self):
            return self._text

        @text.setter
        def text(self, value):
            if not self._text:
                # TODO: apply deleteText
                self._table.update(
                    UpdateReq.delete_text()
                )
            # TODO: apply insertText
            self._table.update(
                UpdateReq.insert_text()
            )
            self._text = value

        @text.deleter
        def text(self):
            self._table.update(
                UpdateReq.delete_text()
            )

    def __init__(self, page, **kwargs):
        table = kwargs.pop('table')
        super(self.__class__, self).__init__(page, **kwargs)

        # initialize metadata
        self.num_rows, self.num_columns = table.get('rows'), table.get('columns')

        # initialize rows and columsn
        self._rows = []
        for row in table.get('tableRows'):
            self._rows.append(
                [self.Cell(self, cell) for cell in row.get('tableCells')]
            )

    def __iter__(self):
        for row in self._rows:
            yield row

    def seek(self, regex):
        """Parses through table cells,
        returning a list of values that
        match given regex pattern.

        :regex: a regular expression <String>
        :returns: a list

        """
        matches = []
        for row in self._rows:
            for cell in row:
                if re.match(regex, cell.text):
                    matches.append(cell.text)

        return matches
