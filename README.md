## What does this repo do?

This project identifies stories that can be materially enhanced by satellite imagery.  Specifically, this project screens all stories from various sources by:

1.  Whether a _geographic entity_ is mentioned within the text.
2.  Whether satellite imagery of the entities could materially enhance the story.

The second screen involves human judgement.  We will ultimately replace human judgement by some sort of nonparametric learning -- which senses which stories are good candidates for further processing (with imagery). Additional, downstream projects will cross-reference the dates and locations with available imagery.

This project is broadly within the **Listen** stage of Overview, where we "listen" to signals in the world to identify stories to surface in our *Where to Look* API. 

**First**, there are four stages to determine whether features within the story can be geolocated:

1. Scrape news stories using [newsapi.org](https://newsapi.org) to extract all the original text.
2. Identify geographic entities using the [IBM Watson APIs](https://www.ibm.com/watson/developercloud/natural-language-understanding/api/v1/).  
3. Geolocate the extracted entities with the [Google Geocode API](https://developers.google.com/maps/documentation/geocoding/intro) (and discard stories without geo-entities).
4. Process the result with additional metadata, including date and entity relevance, and post to [Firebase](https://firebase.google.com).

The **second** stage is a matter of human judgement. This project includes a simple GUI to assist non-technical, internal users to easily determine wehther imagery could potentially enhance the story.  The output of this stage is sorted; and the sorted stories can serve as training data to remove the human component later.  

## How to contribute to this code?

This is primarily a Python project.  We will follow the conventions described in the [Google style guidelines](https://google.github.io/styleguide/pyguide.html).  All secret keys and credentials will be stored as a JSON file and *not* pushed to the master branch, but rather shared on Slack.  

