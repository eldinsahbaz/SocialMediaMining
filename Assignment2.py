#Eldin Sahbaz -- CIS 400 -- Assignment 2

import sys
import time
from urllib2 import URLError
from httplib import BadStatusLine
from functools import partial
from sys import maxint
import json
import twitter
from networkx import *
from operator import itemgetter
import matplotlib.pyplot as plt
from collections import deque

def login():
	CONSUMER_KEY = "4kwvbpYNFKLuJlGOCsz2tdpV8"
	CONSUMER_SECRET = "MBJtx5gO6PdhFkWreCYeS9ivr93eAnlO4uGVikAU0pJRwAYL96"
	OAUTH_TOKEN = "825037296655335425-FFlFTVM8uDgboAK9YfBO5j3cfhHwgT7"
	OAUTH_TOKEN_SECRET = "9LpuESuyI37Y1vrtUPSvnEuZaw1U91MHtbP83GnRy9tM7"
	auth = twitter.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET)
	return twitter.Twitter(auth=auth)

#taken from Twitter Cookbook -- handles http errors
def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):

    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):

        if wait_period > 3600: # Seconds
            print >> sys.stderr, 'Too many retries. Quitting.'
            raise e

        # See https://dev.twitter.com/docs/error-codes-responses for common codes

        if e.e.code == 401:
            print >> sys.stderr, 'Encountered 401 Error (Not Authorized)'
            return None
        elif e.e.code == 404:
            print >> sys.stderr, 'Encountered 404 Error (Not Found)'
            return None
        elif e.e.code == 429:
            print >> sys.stderr, 'Encountered 429 Error (Rate Limit Exceeded)'
            if sleep_when_rate_limited:
                print >> sys.stderr, "Retrying in 15 minutes...ZzZ..."
                sys.stderr.flush()
                time.sleep(60*15 + 5)
                print >> sys.stderr, '...ZzZ...Awake now and trying again.'
                return 2
            else:
                raise e # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print >> sys.stderr, 'Encountered %i Error. Retrying in %i seconds' %                 (e.e.code, wait_period)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function

    wait_period = 2
    error_count = 0

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError, e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError, e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print >> sys.stderr, "URLError encountered. Continuing."
            if error_count > max_errors:
                print >> sys.stderr, "Too many consecutive errors...bailing out."
                raise
        except BadStatusLine, e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print >> sys.stderr, "BadStatusLine encountered. Continuing."
            if error_count > max_errors:
                print >> sys.stderr, "Too many consecutive errors...bailing out."
                raise

#returns the top reciprocal friends
def topReciprocals(twitter_api, screen_name=None, user_id=None, count=5):

    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None),     "Must have screen_name or user_id, but not both"

	#get friends and followers by screen name
    if screen_name:
        friends_ids, followers_ids = get_friends_followers_ids(twitter_api, screen_name=screen_name, friends_limit=5000, followers_limit=5000)
    else: #get friends and followers by ID
        friends_ids, followers_ids = get_friends_followers_ids(twitter_api, user_id=user_id, friends_limit=5000, followers_limit=5000)

    #calculate the intersection of the two sets (reciprocal friends)
    reciprocal = set(friends_ids).intersection(set(followers_ids))

    #get the profiles for each ID in the set of reciprocal friends
    profiles = get_user_profile(twitter_api, user_ids=list(reciprocal))

    #create a new storage container
    followerCount = set()

    #iterate over each profile, extracting the ID and the number of followers
    for prof in profiles:
        followerCount.add((prof, profiles[prof]['followers_count']))

    #return the top 5 friends
    return list(sorted(followerCount, key = itemgetter(1), reverse=True)[0:count])

#taken from Twitter Cookbook -- retrives list of friends/followers
def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None, friends_limit=maxint, followers_limit=maxint):

    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None),     "Must have screen_name or user_id, but not both"

    # See https://dev.twitter.com/docs/api/1.1/get/friends/ids and
    # https://dev.twitter.com/docs/api/1.1/get/followers/ids for details
    # on API parameters

    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
                                count=5000)

    friends_ids, followers_ids = [], []

    for twitter_api_func, limit, ids, label in [
                    [get_friends_ids, friends_limit, friends_ids, "friends"],
                    [get_followers_ids, followers_limit, followers_ids, "followers"]
                ]:

        if limit == 0: continue

        cursor = -1
        while cursor != 0:

            # Use make_twitter_request via the partially bound callable...
            if screen_name:
                #response = make_twitter_request(twitter_api_func, screen_name=screen_name, cursor=cursor)
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else: # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)
                #response = make_twitter_request(twitter_api_func, user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']

            print >> sys.stderr, 'Fetched {0} total {1} ids for {2}'.format(len(ids),
                                                    label, (user_id or screen_name))

            # XXX: You may want to store data during each iteration to provide an
            # an additional layer of protection from exceptional circumstances

            if len(ids) >= limit or response is None:
                break

    # Do something useful with the IDs, like store them to disk...
    return friends_ids[:friends_limit], followers_ids[:followers_limit]

#taken from Twitter Cookbook -- retrieves user profiles
def get_user_profile(twitter_api, screen_names=None, user_ids=None):

    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None),     "Must have screen_names or user_ids, but not both"

    items_to_info = {}

    items = screen_names or user_ids

    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See https://dev.twitter.com/docs/api/1.1/get/users/lookup for details.

        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup,
                                            screen_name=items_str)
        else: # user_ids
            response = make_twitter_request(twitter_api.users.lookup,
                                            user_id=items_str)

        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else: # user_ids
                items_to_info[user_info['id']] = user_info

    return items_to_info

#create twitter API object
twitter_api = login()

#define starting ID
ID = 542024774

#create storage data structures
queue = deque()
seen = set()
G = Graph()
edges = list()

#open file to store data in
fh=open('graph.txt','wb')

#continue until there are at least 100 edges (which means at least 100 nodes)
while len(edges) < 100:
    #get top 5 reciprocal friends
    friends = topReciprocals(twitter_api, user_id=ID)

    #store the friends seen before
    toRemove = list()

    #add any friends seen before to toRemove
    for i in range(len(friends)):
        if friends[i][0] in seen or friends[i][0] in queue:
            toRemove.append(friends[i])

    #remove each friend from the friends list
    for i in toRemove:
        friends.remove(i)

    #even though we've seen them before, we still want to draw an edge
    edges.extend([(ID, friend[0]) for friend in toRemove])

    #draw edges for all the other friends
    edges.extend([(ID, friend[0]) for friend in friends])

    #add friends to queue (for iterating)
    queue.extend([friend[0] for friend in friends])

    #add the current ID to set of seen IDs
    seen.add(ID)

    #get a new ID to process
    ID = queue.popleft()

#draw the edges
G.add_edges_from(edges)

#print graph to file
write_adjlist(G, fh)

#get number of nodes, number of edges, diameter, and average distance of graph
fh.write("\nnumber of nodes: " + str(G.number_of_nodes()) + "\n")
fh.write("number of edges: " + str(G.number_of_edges()) + "\n")
fh.write("diameter: " + str(diameter(G)) + "\n")
fh.write("average distance: " + str(average_shortest_path_length(G)))

#close the files
fh.close()

#draw the graph
draw(G)
plt.show()
