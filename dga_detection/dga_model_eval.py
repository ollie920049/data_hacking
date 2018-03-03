
import os
import sys
import traceback
import optparse
import pickle
import collections
import sklearn
import numpy as np
import tldextract
import math


# Version printing is always a good idea
print 'Scikit Learn version: %s' % sklearn.__version__
print 'TLDExtract version: %s' % tldextract.__version__

# Okay for this model we need the 2LD and nothing else


def domain_extract(url):
    ext = tldextract.extract(url)
    if (not ext.suffix):
        print '(info) Malformed URL: %s' % (url)

    return ext.domain

# Entropy calc (this must match model_gen)


def entropy(s):
    p, lns = collections.Counter(s), float(len(s))
    return -sum(count / lns * math.log(count / lns, 2) for count in p.values())

# Evaluate the incoming domain


def evaluate_url(model, url):

    domain = domain_extract(url)
    alexa_match = model['alexa_counts'] * model['alexa_vc'].transform([url]).T
    dict_match = model['dict_counts'] * model['dict_vc'].transform([url]).T

    # Assemble feature matrix (for just one domain)
    X = [len(domain), entropy(domain), alexa_match, dict_match]
    y_pred = model['clf'].predict(X)[0]
    print '%s : %s' % (domain, y_pred)
    return y_pred

# Evaluate the incoming domains


def evaluate_url_list(model, url_list):

    domain_list = [domain_extract(url) for url in url_list]
    domain_length = [len(domain) for domain in domain_list]
    domain_entropy = [entropy(domain) for domain in domain_list]
    alexa_matches = model['alexa_counts'] * \
        model['alexa_vc'].transform(url_list).T
    dict_matches = model['dict_counts'] * \
        model['dict_vc'].transform(url_list).T

    # Assemble feature matrix
    X = np.array([domain_length, domain_entropy, alexa_matches, dict_matches])
    X = X.T

    # Get the prediction vector
    y_pred = model['clf'].predict(X)
    return y_pred


def load_model_from_disk(name, model_dir='models'):

    # Model directory is relative to this file
    model_path = os.path.join(model_dir, name + '.model')

    # Put a try/except around the model load in case it fails
    try:
        model = pickle.loads(open(model_path, 'rb').read())
    except:
        print 'Could not load model: %s from directory %s!' % (name, model_path)
        return None

    return model


def main():
    ''' Main method, takes care of loading data, running it through the various analyses
        and reporting the results
    '''

    # Handle command-line arguments
    parser = optparse.OptionParser()
    parser.add_option('--input-file', default='data/urls_to_evaluate.txt',
                      help='URL file to pull from.  Default: %default')
    (options, arguments) = parser.parse_args()
    print options, arguments

    try:  # Pokemon exception handling

        # Load up all the models
        print 'Loading Models...'
        clf = load_model_from_disk('dga_model_random_forest')
        alexa_vc = load_model_from_disk('dga_model_alexa_vectorizor')
        alexa_counts = load_model_from_disk('dga_model_alexa_counts')
        dict_vc = load_model_from_disk('dga_model_dict_vectorizor')
        dict_counts = load_model_from_disk('dga_model_dict_counts')
        model = {'clf': clf, 'alexa_vc': alexa_vc, 'alexa_counts': alexa_counts,
                 'dict_vc': dict_vc, 'dict_counts': dict_counts}

        # Examples (feel free to change these and see the results!)
        evaluate_url(model, 'www.google.com')
        evaluate_url(model, 'www.facebook.com')
        evaluate_url(model, 'www.1cb8a5f36f.com')

        # Now evaluate all the domains in the input file (assumed one domain per line)
        with open(options.input_file) as input_urls:
            url_list = [url.strip() for url in input_urls]

        # Evaluate all the domains at the same time (much more efficient than one at a time)
        results = evaluate_url_list(model, url_list)
        for url, result in zip(url_list, results):
            print '%s: %s' % (url, result)

    except KeyboardInterrupt:
        print 'Goodbye Cruel World...'
        sys.exit(0)
    except Exception, error:
        traceback.print_exc()
        print '(Exception):, %s' % (str(error))
        sys.exit(1)


if __name__ == '__main__':
    main()
