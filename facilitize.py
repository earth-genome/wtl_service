
import config
from watson_developer_cloud import NaturalLanguageUnderstandingV1
import watson_developer_cloud.natural_language_understanding_v1 as natty


# Defines a global set of words that are repeatedly surfaced as facilities,
# even though we don't want to include them.  Add new facilies as a separate
# line (without quotations) to bad_list.txt
with open ("bad_list.txt", "r") as badfile:
    data = badfile.readlines()
    BAD_SET = set([x.strip() for x in data])


def entity_extraction(text):
	# Accepts a string of text (without special characters) and returns all
	# entities as identified by the IBM Watson developer APIs.  These entities
	# are returned as a list of people, places, and things, which will be
	# filtered to just find 'Facilities' or 'Geographic Features'
	nlu = NaturalLanguageUnderstandingV1(
		version='2017-02-27',
		username=config.WATSON_USER,
		password=config.WATSON_PASS
	)

	x = nlu.analyze(
		text=text,
		features=natty.Features(
			entities=natty.EntitiesOptions(), 
			keywords=natty.KeywordsOptions()
		)
	)

	return x['entities']


def acceptable_entity(entity):
	# Returns True if the supplied entity is acceptable, i.e., a facility or
	# geographic feature AND not in the bad list.  Else False.
	if entity['type'] in ['Facility', 'GeographicFeature', 'NaturalEvent']:
		if entity['text'] not in BAD_SET:
			return True
	else:
		return False




# [e for e in entities if acceptable_entity(e)]
