
import watson_developer_cloud as wdc
import watson_developer_cloud.natural_language_understanding.features.v1 as fts


def badwords():
	# Returns a set of words that are repeatedly surfaced as facilities, even
	# though we don't want to include them.  Add new facilies as a separate
	# line (without quotations) to bad_list.txt
	with open ("bad_list.txt", "r") as badfile:
	    data = badfile.readlines()
	    return set([x.strip() for x in data])


def entity_extraction():
