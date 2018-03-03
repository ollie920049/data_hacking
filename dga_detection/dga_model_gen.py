import os
import sys
import traceback
import optparse
import pickle
import collections
import sklearn
import sklearn.feature_extraction
import sklearn.ensemble
import sklearn.metrics
import pandas as pd
import numpy as np
import tldextract
import math

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Version printing is always a good idea
print('Scikit Learn version: %s' % sklearn.__version__)
print('Pandas version: %s' % pd.__version__)
print('TLDExtract version: %s' % tldextract.__version__)


def domain_extract(uri):
    ext = tldextract.extract(uri)
    if (not ext.suffix):
        return None
    else:
        return ext.domain


def entropy(s):
    p, lns = collections.Counter(s), float(len(s))
    return -sum(count / lns * math.log(count / lns, 2) for count in p.values())


def show_cm(cm, labels):
    percent = (cm * 100.0) / np.array(np.matrix(cm.sum(axis=1)).T)

    print('Confusion Matrix Stats')
    for i, label_i in enumerate(labels):
        for j, label_j in enumerate(labels):
            print("%s/%s: %.2f%% (%d/%d)" % (label_i, label_j, (percent[i][j]), cm[i][j], cm[i].sum()))


def save_model_to_disk(name, model, model_dir='models'):
    ''' Serialize and save a model to disk'''

    # First serialized the model
    serialized_model = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)

    # Model directory + model name
    model_path = os.path.join(model_dir, name + '.model')

    # Now store it to disk
    print('Storing Serialized Model to Disk (%s:%.2fMeg)' % (name, len(serialized_model) / 1024.0 / 1024.0))
    open(model_path, 'wb').write(serialized_model)


def load_model_from_disk(name, model_dir='models'):

    # Model directory is relative to this file
    model_path = os.path.join(model_dir, name + '.model')

    # Put a try/except around the model load in case it fails
    try:
        model = pickle.loads(open(model_path, 'rb').read())
    except Exception:
        print('Could not load model: %s from directory %s!' % (name, model_path))
        return None

    return model


def main():
    ''' Main method, takes care of loading data, running it through the various analyses
        and reporting the results
    '''

    # Handle command-line arguments
    parser = optparse.OptionParser()
    parser.add_option('--alexa-file', default='data/alexa_100k.csv',
                      help='Alexa file to pull from.  Default: %default')
    (options, arguments) = parser.parse_args()
    print(options, arguments)

    try:  # Pokemon exception handling

        # This is the Alexa 1M domain list.
        print('Loading alexa dataframe...')
        alexa_dataframe = pd.read_csv(options.alexa_file, names=[
                                      'rank', 'uri'], header=None, encoding='utf-8')
        print(alexa_dataframe.info())
        print(alexa_dataframe.head())

        # Compute the 2LD of the domain given by Alexa
        alexa_dataframe['domain'] = [domain_extract(
            uri) for uri in alexa_dataframe['uri']]
        del alexa_dataframe['rank']
        del alexa_dataframe['uri']
        alexa_dataframe = alexa_dataframe.dropna()
        alexa_dataframe = alexa_dataframe.drop_duplicates()
        print(alexa_dataframe.head())

        # Set the class
        alexa_dataframe['class'] = 'legit'

        # Shuffle the data (important for training/testing)
        alexa_dataframe = alexa_dataframe.reindex(
            np.random.permutation(alexa_dataframe.index))
        alexa_total = alexa_dataframe.shape[0]
        print('Total Alexa domains %d' % alexa_total)

        # Read in the DGA domains
        dga_dataframe = pd.read_csv(
            'data/dga_domains.txt', names=['raw_domain'], header=None, encoding='utf-8')

        # We noticed that the blacklist values just differ by captilization or .com/.org/.info
        dga_dataframe['domain'] = dga_dataframe.applymap(
            lambda x: x.split('.')[0].strip().lower())
        del dga_dataframe['raw_domain']

        # It's possible we have NaNs from blanklines or whatever
        dga_dataframe = dga_dataframe.dropna()
        dga_dataframe = dga_dataframe.drop_duplicates()
        dga_total = dga_dataframe.shape[0]
        print('Total DGA domains %d' % dga_total)

        # Set the class
        dga_dataframe['class'] = 'dga'

        print('Number of DGA domains: %d' % dga_dataframe.shape[0])
        print(dga_dataframe.head())

        # Concatenate the domains in a big pile!
        all_domains = pd.concat(
            [alexa_dataframe, dga_dataframe], ignore_index=True)

        # Add a length field for the domain
        all_domains['length'] = [len(x) for x in all_domains['domain']]

        # Okay since we're trying to detect dynamically generated domains and short
        # domains (length <=6) are crazy random even for 'legit' domains we're going
        # to punt on short domains (perhaps just white/black list for short domains?)
        all_domains = all_domains[all_domains['length'] > 6]

        # Add a entropy field for the domain
        all_domains['entropy'] = [entropy(x) for x in all_domains['domain']]
        print(all_domains.head())

        # Now we compute NGrams for every Alexa domain and see if we can use the
        # NGrams to help us better differentiate and mark DGA domains...

        # Scikit learn has a nice NGram generator that can generate either char NGrams or word NGrams (we're using char).
        # Parameters:
        #       - ngram_range=(3,5)  # Give me all ngrams of length 3, 4, and 5
        #       - min_df=1e-4        # Minimumum document frequency. At 1e-4 we're saying give us NGrams that
        #                            # happen in at least .1% of the domains (so for 100k... at least 100 domains)
        alexa_vc = sklearn.feature_extraction.text.CountVectorizer(
            analyzer='char', ngram_range=(3, 5), min_df=1e-4, max_df=1.0)

        # I'm SURE there's a better way to store all the counts but not sure...
        # At least the min_df parameters has already done some thresholding
        counts_matrix = alexa_vc.fit_transform(alexa_dataframe['domain'])
        alexa_counts = np.log10(counts_matrix.sum(axis=0).getA1())
        ngrams_list = alexa_vc.get_feature_names()

        # For fun sort it and show it
        import operator
        _sorted_ngrams = sorted(
            zip(ngrams_list, alexa_counts), key=operator.itemgetter(1), reverse=True)
        print('Alexa NGrams: %d' % len(_sorted_ngrams))
        for ngram, count in _sorted_ngrams[:10]:
            print(ngram, count)

        # We're also going to throw in a bunch of dictionary words
        word_dataframe = pd.read_csv(
            'data/words.txt', names=['word'], header=None, dtype={'word': np.str}, encoding='utf-8')

        # Cleanup words from dictionary
        word_dataframe = word_dataframe[word_dataframe['word'].map(
            lambda x: str(x).isalpha())]
        word_dataframe = word_dataframe.applymap(
            lambda x: str(x).strip().lower())
        word_dataframe = word_dataframe.dropna()
        word_dataframe = word_dataframe.drop_duplicates()
        print(word_dataframe.head(10))

        # Now compute NGrams on the dictionary words
        # Same logic as above...
        dict_vc = sklearn.feature_extraction.text.CountVectorizer(
            analyzer='char', ngram_range=(3, 5), min_df=1e-5, max_df=1.0)
        counts_matrix = dict_vc.fit_transform(word_dataframe['word'])
        dict_counts = np.log10(counts_matrix.sum(axis=0).getA1())
        ngrams_list = dict_vc.get_feature_names()

        # For fun sort it and show it
        import operator
        _sorted_ngrams = sorted(
            zip(ngrams_list, dict_counts), key=operator.itemgetter(1), reverse=True)
        print('Word NGrams: %d' % len(_sorted_ngrams))
        for ngram, count in _sorted_ngrams[:10]:
            print(ngram, count)

        # We use the transform method of the CountVectorizer to form a vector
        # of ngrams contained in the domain, that vector is than multiplied
        # by the counts vector (which is a column sum of the count matrix).
        def ngram_count(domain):
            # Woot vector multiply and transpose Woo Hoo!
            alexa_match = alexa_counts * alexa_vc.transform([domain]).T
            dict_match = dict_counts * dict_vc.transform([domain]).T
            print('%s Alexa match:%d Dict match: %d' % (domain, alexa_match, dict_match))

        # Examples:
        ngram_count('google')
        ngram_count('facebook')
        ngram_count('1cb8a5f36f')
        ngram_count('pterodactylfarts')
        ngram_count('ptes9dro-dwacty2lfa5rrts')
        ngram_count('beyonce')
        ngram_count('bey666on4ce')

        # Compute NGram matches for all the domains and add to our dataframe
        all_domains['alexa_grams'] = alexa_counts * \
            alexa_vc.transform(all_domains['domain']).T
        all_domains['word_grams'] = dict_counts * \
            dict_vc.transform(all_domains['domain']).T
        print(all_domains.head())

        # Use the vectorized operations of the dataframe to investigate differences
        # between the alexa and word grams
        all_domains['diff'] = all_domains['alexa_grams'] - \
            all_domains['word_grams']

        # The table below shows those domain names that are more 'dictionary' and less 'web'
        print(all_domains.sort_values(['diff'], ascending=True).head(10))

        # The table below shows those domain names that are more 'web' and less 'dictionary'
        # Good O' web....
        print(all_domains.sort_values(['diff'], ascending=False).head(50))

        # Lets look at which Legit domains are scoring low on both alexa and word gram count
        weird_cond = (all_domains['class'] == 'legit') & (
            all_domains['word_grams'] < 3) & (all_domains['alexa_grams'] < 2)
        weird = all_domains[weird_cond]
        print(weird.shape[0])
        print(weird.head(10))

        # Epiphany... Alexa really may not be the best 'exemplar' set...
        #             (probably a no-shit moment for everyone else :)
        #
        # Discussion: If you're using these as exemplars of NOT DGA, then your probably
        #             making things very hard on your machine learning algorithm.
        #             Perhaps we should have two categories of Alexa domains, 'legit'
        #             and a 'weird'. based on some definition of weird.
        #             Looking at the entries above... we have approx 80 domains
        #             that we're going to mark as 'weird'.
        #
        all_domains.loc[weird_cond, 'class'] = 'weird'
        print(all_domains['class'].value_counts())
        all_domains[all_domains['class'] == 'weird'].head()

        # Perhaps we will just exclude the weird class from our ML training
        not_weird = all_domains[all_domains['class'] != 'weird']
        X = not_weird.as_matrix(
            ['length', 'entropy', 'alexa_grams', 'word_grams'])

        # Labels (scikit learn uses 'y' for classification labels)
        y = np.array(not_weird['class'].tolist())

        # Random Forest is a popular ensemble machine learning classifier.
        # http://scikit-learn.org/dev/modules/generated/sklearn.ensemble.RandomForestClassifier.html
        clf = sklearn.ensemble.RandomForestClassifier(
            n_estimators=20)  # Trees in the forest

        # Train on a 80/20 split
        from sklearn.cross_validation import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2)
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        # Now plot the results of the holdout set in a confusion matrix
        labels = ['legit', 'dga']
        cm = sklearn.metrics.confusion_matrix(y_test, y_pred, labels)
        show_cm(cm, labels)

        # We can also look at what features the learning algorithm thought were the most important
        importances = zip(['length', 'entropy', 'alexa_grams',
                           'word_grams'], clf.feature_importances_)
        print(importances)

        # Now train on the whole thing before doing tests and saving models to disk
        clf.fit(X, y)

        # test_it shows how to do evaluation, also fun for manual testing below :)
        def test_it(domain):

            # Woot matrix multiply and transpose Woo Hoo!
            _alexa_match = alexa_counts * alexa_vc.transform([domain]).T
            _dict_match = dict_counts * dict_vc.transform([domain]).T
            _X = np.array([len(domain), entropy(domain), _alexa_match, _dict_match]).reshape(1, -1)
            print('%s : %s' % (domain, clf.predict(_X)[0]))

        # Examples (feel free to change these and see the results!)
        test_it('google')
        test_it('google88')
        test_it('facebook')
        test_it('1cb8a5f36f')
        test_it('pterodactylfarts')
        test_it('ptes9dro-dwacty2lfa5rrts')
        test_it('beyonce')
        test_it('bey666on4ce')
        test_it('supersexy')
        test_it('yourmomissohotinthesummertime')
        test_it('35-sdf-09jq43r')
        test_it('clicksecurity')

        # Serialize model to disk
        save_model_to_disk('dga_model_random_forest', clf)
        save_model_to_disk('dga_model_alexa_vectorizor', alexa_vc)
        save_model_to_disk('dga_model_alexa_counts', alexa_counts)
        save_model_to_disk('dga_model_dict_vectorizor', dict_vc)
        save_model_to_disk('dga_model_dict_counts', dict_counts)

    except KeyboardInterrupt:
        print('Goodbye Cruel World...')
        sys.exit(0)
    except Exception as error:
        traceback.print_exc(())
        print('(Exception):, %s' % (str(error)))
        sys.exit(1)


if __name__ == '__main__':
    main()
