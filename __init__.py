#-------------------------------------------------------------------------------
# Name:        solr_search
# Purpose:
#
# Author:      Jeremy Nelson
#
# Created:     2014-01-30
# Copyright:   (c) Jeremy Nelson, Colorado College 2014
# Licence:     MIT
#-------------------------------------------------------------------------------
import json
from solr import SearchHandler
try:
    from catalog.mongo_datastore import check_for_cover_art, get_item_details
except ImportError:
    from mongo_datastore import check_for_cover_art, get_item_details

from flask.ext.solrpy import FlaskSolrpy
from flask import Blueprint, flash, g, jsonify, request, render_template
from flask import session, url_for

from forms import BasicSearch
try:
    from helpers.tutt_maps import FULL_CODE_MAP
except ImportError:
    FULL_CODE_MAP = {}

solr_search = Blueprint('solr_search', __name__, static_folder='static')
solr = FlaskSolrpy()

@solr_search.route('/search',
                   methods=['GET', 'POST'])
def search():
    query = request.form.get('q')
    page = request.form.get('page', 0)
    solr_result = g.solr.select(query,
                                **{'q.op': 'AND',
                                   'rows': 8,
                                   'start': page})
    for row in solr_result.results:
        if '__version__' in row:
            row.pop('__version__')
        print(row)
        row['workURL'] = url_for('work',
                                 work_id=row['id'])
        if check_for_cover_art(row['id']):
            row['coverURL'] = url_for('cover_art',
                                       cover_id=row['id'])
        else:
            row['coverURL'] = url_for('solr_search.static',
                                      filename='img/no-cover.png')
        if 'location' in row:
            location_code = row.pop("location")[0]
            row['instanceLocation'] = FULL_CODE_MAP.get(location_code,
                                                        location_code)

        row['instanceDetail'] = get_item_details(row['id'])
        if 'author' in row:
            row['author'].insert(0, 'by ')
        else:
            row['author'] = []
    if solr_result.start < 1:
        page = 1
    else:
        page = solr_result.start
    return jsonify({'total': solr_result.numFound,
                    'instances': solr_result.results,
                    'page': page,
                    'result': "OK"})

@solr_search.route('/suggest',
           methods=['GET', 'POST'])
def suggest():
    solr_suggest = SearchHandler(g.solr, "/suggest")
    if 'prefetch' in request.args:

        return jsonify({'value': 'a'})
    query = request.args.get('q')
    solr_result = json.loads(solr_suggest.raw(q=query, wt='json'))
    if len(solr_result['spellcheck']['suggestions']) > 0:
        suggestions = solr_result['spellcheck']['suggestions'][1]['suggestion']
        return json.dumps(map(lambda x: {'value': x}, suggestions))
    return jsonify({})
    #return jsonify(results=map(lambda x: {'value': x}, suggestions))

def __get_fields_subfields__(marc_rec,
                             fields,
                             subfields,
                             unique=True):
    output = []
    for field in marc_rec.get('fields'):
        tag = field.keys()[0]
        if fields.count(tag) > 0:
            for row in field[tag]['subfields']:
                subfield = row.keys()[0]
                if subfields.count(subfield) > 0:
                    output.append(row[subfield])
    if unique:
        output = list(set(output))
    return output

def __get_title__(marc):
    title_row = __get_fields_subfields__(marc, ["245"], ["a", "b"], False)
    return ''.join(title_row)

def index_marc(solr_connection,
               marc):
    """Function takes a MARC JSON dict and indexes it into a Solr index.

    :param solr_connection: Solr.py Connection
    :param marc: JSON MARC record
    """
    record_info = marc.pop('recordInfo')
    solr_connection.add(id=str(marc.get("_id")),  # Usually MongoDB ID
                        author=__get_fields_subfields__(marc,
                                               ["100", "110", "111"],
                                               ["a"]),
                        location=__get_fields_subfields__(marc,
                                                ["994"],
                                                ["a"]),
                        topics=__get_fields_subfields__(marc,
                                               ['600', '610', '611', '630',
                                                '648', '650', '651', '653',
                                                '654', '655', '656', '657',
                                                '658', '662', '690', '691',
                                                '696', '697', '698', '699'],
                                                ['a', 'v', 'x', 'y', 'z']),
                        title=__get_title__(marc),
                        text=str(marc))


def index_mods(solr_connection,
               schema_entity,
               raw_mods):
    """Function indexes a raw MODS xml document along with metadata into Solr

    Args:
        solr_connection: Solr.py Connection
        schema_entity: Schema.org JSON metadata for the main work
        raw_mods: Raw XML of MODS

    Returns:
        None

    Raises:
        None
    """
    if 'recordInfo' in schema_entity:
        record_info = schema_entity.pop('recordInfo')
    solr_connection.add(id=str(schema_entity.get('_id')),
                        author=schema_entity.get('author'),
                        location=schema_entity.get('availableAtOrFrom', None),
                        topics=schema_entity.get('keywords'),
                        title=schema_entity.get('headline'),
                        text=raw_mods)

def main():
    pass

if __name__ == '__main__':
    main()
