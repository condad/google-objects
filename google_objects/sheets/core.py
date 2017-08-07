# -*- coding: utf-8 -*-

"""

Google Sheets API
    Mon Sep 19 21:10:28 2016

"""

import logging

from .. import GoogleClient, GoogleObject
from ..utils import keys_to_snake

log = logging.getLogger(__name__)


# TODO:
    # i/ ensure all cell data reflects table row insertion and deletion
    # ii/ page title and descriptor need to be found and initialized
    # iii/ change .from_existing to .from_raw


def _value_to_cell(val):
    if val.isdigit():
        try:
            return {'userEnteredValue': {'numberValue': float(val)}}
        except:
            return {'userEnteredValue': {'numberValue': int(val)}}
    return {'userEnteredValue': {'stringValue': val}}


def _cells_to_row(cells):
    return [_value_to_cell(cell) for cell in cells]


def _format_sheet(sheet):
    title = sheet.get('title', 'NEW SHEET')
    values = sheet.get('values', [])
    return {
        'properties': {
            'title': title
        },
        'data': {
            'rowData': [{'values': _cells_to_row(val)} for val in values]
        }
    }


def _grid_to_a1(sheet_name, start, end):
    start_row, start_col = start
    end_row, end_col = end

    start_row_a1 = start_row + 1
    start_col_a1 = chr(start_col % 26 + 65)
    end_row_a1 = end_row
    end_col_a1 = chr(end_col % 26 + 64)

    return '\'{}\'!{}{}:{}{}'.format(
        sheet_name, start_col_a1, start_row_a1,
        end_col_a1, end_row_a1
    )


class SheetsClient(GoogleClient):

    """Creates a Google Sheets Resource"""

    @classmethod
    def from_service_account(cls, **kwargs):
        kwargs['scope'] = ['spreadsheets']
        kwargs['service'] = ['sheets']
        kwargs['version'] = ['v4']
        return super().from_service_account(**kwargs)

    def get_spreadsheet(self, id):
        """Returns a Spreadsheet Object

        :id: Spreadsheet ID
        :returns: <Spreadsheet> Model

        """
        data = self.resource.spreadsheets().get(
            spreadsheetId=id
        ).execute()

        return Spreadsheet.from_existing(data, self)

    def create_spreadsheet_from_dataframes(self, *frames, **options):
        if not frames:
            raise ValueError

        formatted_frames = [frm.values.tolist() for frm in frames]
        return self.create_spreadsheet(self, formatted_frames, **options)

    def create_spreadsheet(self, sheets=[], **kwargs):
        data = self.resource.spreadsheets().create(
            body={
                'properties': kwargs,
                'sheets': [_format_sheet(s) for s in sheets]
            }
        ).execute()

        return Spreadsheet.from_existing(data, self)

    def get_values(self, spreadsheet_id, range_name):
        """Initialize a new block and return it"""

        data = self.resource.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()

        return Block.from_existing(data, client=self)

    def update_values(self, spreadsheet_id, range_name, values, format='RAW'):
        data = self.resource.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=format,
            body={'values': values}
        ).execute()

        return data

    def append_values(self, spreadsheet_id, rng, values):
        """Append Values to Range.

        :spreadsheet: Google Spreadsheet ID
        :range: Range in A1 Notation
        :returns: None

        """

        data = self.resource.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=rng,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': values}
        ).execute()

        return Block.from_existing(data, client=self)

    def push_updates(self, spreadsheet_id, updates):
        spreadsheets = self.resource.spreadsheets()
        spreadsheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': updates}
        ).execute()


class Spreadsheet(GoogleObject):

    """Represents a Google API Spreadsheet object"""

    def __init__(self, client=None, **kwargs):
        """Creates a new Spreadsheet Object"""

        self.client = client
        self.__updates = []

        # initalize the other properties
        super(self.__class__, self).__init__(**kwargs)

    def __iter__(self):
        return self.yield_sheets()

    def __getitem__(self, key):
        try:
            if key.isdigit():
                return self.get_sheet_by_id(key)
            else:
                return self.get_sheet_by_name(key)
        except ValueError:
            raise TypeError('Sheet not found')

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.update()

    @classmethod
    def from_existing(cls, data, client=None):
        """initiates using existing Spreadsheet resource"""

        new_data = keys_to_snake(data)
        return cls(client, **new_data)

    @property
    def id(self):
        return self._spreadsheet_id

    @property
    def title(self):
        return self._properties.get('title')

    @title.setter
    def title(self, value):
        self._properties['title'] = value

    def sheets(self):
        return [sheet for sheet in self.yield_sheets()]

    def get_sheet_by_id(self, sheet_id):
        """Returns sheet within presentation identified
        by the given argument, raises TypeError
        if such element isn't present.
        """
        for sheet in self.yield_sheets():
            if sheet_id == sheet.id:
                return sheet

        raise ValueError

    def get_sheet_by_name(self, name):
        for sheet in self.yield_sheets():
            if name == sheet.title:
                return sheet

        raise ValueError

    def yield_sheets(self):
        for sheet in self._sheets:
            yield Sheet.from_existing(sheet, self)

    def get_range(self, sheet_range):
        """Takes a sheet range and initializes a block object
        with the raw data and the spreadsheet for update
        functionality.
        """
        return self.client.get_values(self.id, sheet_range)

    def get_named_range_by_name(self, rng_name):
        """Return <NamedRange> instance by id."""

        for rng in self.named_ranges():
            if rng_name == rng.name:
                return rng

    def get_named_range_by_id(self, rng_id):
        """Return <NamedRange> instance by id."""

        for rng in self.named_ranges():
            if rng_id == rng.id:
                return rng

    def named_ranges(self):
        def set_sheet_id(rng):
            """If sheet_id isn't present, set it to the ID of the first sheet.
            """
            if 'sheet_id' not in rng['range']:
                rng['range']['sheet_id'] = 0

            return rng

        _named_ranges = map(set_sheet_id, self._named_ranges)
        return [NamedRange(self, each) for each in _named_ranges]

    def update(self):
        if self.__updates:
            self.client.push_updates(self._id, self._updates)
            # TODO: add success handlers
            del self._updates[:]


class NamedRange(object):

    """represents a NamedRange resource, can
    return it's range in A1 notation
    """

    def __init__(self, spreadsheet, named_range):
        self.spreadsheet = spreadsheet
        self.id = named_range.get('named_range_id')
        self.name = named_range.get('name')
        self.range = named_range.get('range')

    @property
    def sheet_id(self):
        if 'sheet_id' in self.range:
            return self.range['sheet_id']

    @property
    def sheet_name(self):
        sheet = self.spreadsheet[self.sheet_id]
        return sheet.title

    @property
    def start_row(self):
        if 'start_row_index' in self.range:
            return self.range['start_row_index']

    @property
    def end_row(self):
        if 'end_row_index' in self.range:
            return self.range['end_row_index']

    @property
    def start_column(self):
        if 'start_column_index' in self.range:
            return self.range['start_column_index']

    @property
    def end_column(self):
        if 'end_column_index' in self.range:
            return self.range['end_column_index']

    def as_a1(self):
        sheet_name = None
        for sheet in self.spreadsheet.sheets():
            if self.sheet_id == sheet.id:
                sheet_name = sheet.title
                break

        start = (self.start_row, self.start_column)
        end = (self.end_row, self.end_column)
        return _grid_to_a1(sheet_name, start, end)

    def get_block(self):
        return self.spreadsheet.get_range(self.as_a1())


class Sheet(GoogleObject):

    """Represents a Google API Sheet object,
    there is little functionality associated with
    this object, it will be mostly used as reference for
    initializing blocks.
    """

    def __init__(self, spreadsheet=None, **kwargs):
        """Creates a new Sheet Object"""
        self.spreadsheet = spreadsheet

        # initalize the other properties
        super(self.__class__, self).__init__(**kwargs)

        self.properties = kwargs.get('properties', {})

    @classmethod
    def from_existing(cls, data, spreadsheet):
        """initiates using existing Sheet resource"""

        new_data = keys_to_snake(data)
        return cls(spreadsheet, **new_data)

    @property
    def properties(self):
        return self._properties

    @properties.setter
    def properties(self, value):
        if 'sheet_id' in value:
            self._properties['sheet_id'] = value['sheet_id']

        if 'title' in value:
            self._properties['title'] = value['title']

    @property
    def id(self):
        return self._properties.get('sheet_id')

    @property
    def title(self):
        return self._properties.get('title')

    @property
    def name(self):
        return self.title

    @title.setter
    def title(self, value):
        self._properties['title'] = value

    def values(self, start=None, end=None):
        """Returns <Block> consisting of all sheet data"""

        block = self.spreadsheet.get_range(self.title)
        block.spreadsheet = self.spreadsheet

        return block


class Block(GoogleObject):

    """Recieves a dictionary corresponding to a
    ValueRange in Google Sheets and provides methods related
    to modification and formatting.
    """

    def __init__(self, client=None, spreadsheet=None, **kwargs):
        self.client = client
        self.spreadsheet = spreadsheet

        # initalize the other properties
        super(self.__class__, self).__init__(**kwargs)

    @classmethod
    def from_existing(cls, data, client, spreadsheet=None):
        """initiates using existing ValueRange resource"""

        new_data = keys_to_snake(data)
        return cls(client, spreadsheet, **new_data)

    def __iter__(self):
        return self.yield_rows()

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_val, tb):
        self.update()

    def update(self):
        self.client.update_values(self.spreadsheet.id, self._range, self.values)

    def append(self, data):
        self.client.append_values(self.spreadsheet.id, self._range, data)

    def yield_cells(self):
        for row in self.yield_rows():
            for cell in row:
                yield cell

    @property
    def cells(self):
        return [cell for cell in self.yield_cells()]

    def yield_rows(self):
        for row in self._values:
            yield row

    @property
    def rows(self):
        return [row for row in self.yield_rows()]

    @property
    def values(self):
        return self._values

    @property
    def raw_data(self):
        # legacy, will be deprecated soon
        return self.values

    @property
    def range(self):
        return self._range

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key, item):
        self._values[key] = item
