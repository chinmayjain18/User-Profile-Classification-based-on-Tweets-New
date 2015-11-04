import dataStructures
import classifier

import pickle
import os

from textblob import TextBlob

import argparse

from enum import Enum

# Possible classes for education
class EDUCATION_CLASS(Enum):
    high_school = 0
    some_college = 1
    graduate = 2

def _getEducationFromString(user_education):
    '''
    Args:
        input: Input string from user response for education level
    Returns:
        EDUCATION_CLASS of user, or None for not sure
    '''
    hs_keywords = ['high']
    sc_keywords = ['bachelor', 'college', 'bs', 'ba']
    g_keywords = ['doctoral', 'phd', 'ma', 'master', 'graduate', 'mba', 'mlis']
    if not user_education:
        return None
    else:
        user_education = user_education.lower()
        for keyword in hs_keywords:
            if keyword in user_education:
                return EDUCATION_CLASS.high_school.value
        for keyword in sc_keywords:
            if keyword in user_education:
                return EDUCATION_CLASS.some_college.value
        for keyword in g_keywords:
            if keyword in user_education:
                return EDUCATION_CLASS.graduate.value
    return None

# Input:
# files = list of strings of filenames in a directory
# filename = string of file we are looking for.
# Returns:
# None if file is not found, otherwise, returns filename of file that was looked for.
def check_for_file(files, filename):
    if filename in files:
        index = files.index(filename)
        return files[index]
    else:
        return None

# Input:
# root = root directory that file is in.
# filename = file we are going to open
# Returns:
# None if filename is none, otherwise, returns unpickled_data from file.
def unpickle_from_filename(root, filename):
    if filename is None:
        return None
    else:
        unpickled_data = pickle.load(open(os.path.join(root, filename), "rb"))
        return unpickled_data

# Input:
# data_folder = string, foldername we are going to recursively traverse.
# Returns:
# List of User objects. There should be a User object per subfolder.
def load_data(data_folder):
    user_list = []
    for root, sub_folders, files in os.walk(data_folder):
        if root == ".DS_Store" or root == data_folder:
            continue
        ngramsFile = check_for_file(files, 'ngrams.pickl')
        replacementsFile = check_for_file(files, 'replacements.pickl')
        transformsFile = check_for_file(files, 'transforms.pickl')
        tweetsFile = check_for_file(files, 'tweets.pickl')
        userFile = check_for_file(files, 'user.pickl')

        ngrams = unpickle_from_filename(root, ngramsFile)
        replacements = unpickle_from_filename(root, replacementsFile)
        transforms = unpickle_from_filename(root, transformsFile)
        tweets = unpickle_from_filename(root, tweetsFile)
        userInfo = unpickle_from_filename(root, userFile)

        # Take tweets dictionary and turn to Tweet objects.
        tweets_list = []
        if tweets is not None:
            for tweetId, value in tweets.items():
                tweet = dataStructures.Tweet(id=tweetId, tokens=value["tokenized"], timestamp=value["time"], rawText=value["text"], numTokens=value["tokens"], numPunctuation=value["punc"])
                tweets_list.append(tweet)

        user = dataStructures.User(id=root, tweets=tweets_list, ngrams=ngrams, replacements=replacements, transforms=transforms)
        if userInfo is not None:
            for key, value in userInfo.items():
                if key == 'Education':
                    setattr(user, key.lower(), _getEducationFromString(value))
                else:
                    setattr(user, key.lower(), value)
        user_list.append(user)
    return user_list

def calculate_features(user_list):
    '''
    Calculates the features for each user in user_list
    Args:
        user_list: List of users
    Returns:
        calculated_features: list of dictionaries of features for each user
        in user_list in the same order as user_list
    '''
    calculated_features = []

    for user in user_list:

        features = []
        features.append(dataStructures.AverageTweetLengthFeature(user))
        features.append(dataStructures.NumberOfTimesOthersMentionedFeature(user))
        features.append(dataStructures.CountLanguageUsed(user))
        features.append(dataStructures.AgeOccupation(user))

        user_dict = {}
        for feature in features:
            user_dict[feature.getKey()] = feature.getValue()

        tweet_dict = {}
        for tweet in user.tweets:

            tweet_features = []
            tweetTB = TextBlob(tweet.rawText)

            tweet_features.append(dataStructures.CountCategoricalWords(tweet))
            tweet_features.append(dataStructures.CountPersonalReferences(tweetTB))

            for tweet_feature in tweet_features:
                key = tweet_feature.getKey()
                if not key in tweet_dict.keys():
                    tweet_dict[key] = 0
                tweet_dict[key] += tweet_feature.getValue()

        # Merge tweet-level dic (summed) values into user dic
        user_dict.update(tweet_dict)

        # Merge in time vectors from that feature
        time_vector_feature = dataStructures.FrequencyOfTweetingFeature(user)
        user_dict.update(time_vector_feature.getValue())

        # Add the user dictionary to the features list.
        calculated_features.append(user_dict)

    return calculated_features

def _testAccuracy(display_type, classes, features):
    '''
    Tests the accuracy, prints results.
    Args:
        display_type: String value of type to be displayed in print message (eg. 'gender')
        train_classes: list of user's classes to train on (eg. genders)
        train_features: corrisponding list of user's computed features
        test_classes: list of user's classes to test on (eg. genders)
        test_features: corrisponding list of user's computed features
    '''

    ACC_STRING = '\t{1} {0} accuracy: {2}'
    TEST_RATIO = 0.75
    split_index = int(len(classes) * TEST_RATIO)

    train_classes, test_classes = classes[:split_index], classes[split_index:]
    train_features, test_features = features[:split_index], features[split_index:]

    # SVM
    acc = classifier.get_SVM_Acc(train_features, train_classes, test_features, test_classes)
    print(ACC_STRING.format(display_type, 'SVM', acc))

    # Naive Bayes
    acc = classifier.get_Naivebayes_Acc(train_features, train_classes, test_features, test_classes)
    print(ACC_STRING.format(display_type, 'Naive Bayes', acc))

    # Linear Regression
    acc = classifier.get_LinearRegression_Acc(train_features, train_classes, test_features, test_classes)
    print(ACC_STRING.format(display_type, 'Linear Regression', acc))

    print("")

def _filterFeatures(whitelist, features_list):
    '''
    Filters out every features that isn't on the whitelist
    Args:
        whitelist: list of strings of the feature keys to keep
        features: list of dictionaries of features
    Returns:
        list of dictionaries of features
    '''
    reduced_list = []
    for features in features_list:
        reduced_list.append({ key: features[key] for key in whitelist })
    return reduced_list

def main():

    parser = argparse.ArgumentParser(description='Problem Set 3')
    parser.add_argument('data_folder', help='path to data folder')
    parser.add_argument('-v', help='verbose mode')

    args = parser.parse_args()

    verbose_mode = bool(args.v)

    user_list = load_data(args.data_folder)

    calculated_features = calculate_features(user_list)

    if verbose_mode:
        print(len(calculated_features))
        print(calculated_features)

    user_genders = []
    gender_features = []
    gender_whitelist = [
        'AverageTweetLength'
    ]

    user_educations = []
    education_features = []
    education_whitelist = [
        'AverageTweetLength'
    ]

    user_ages = []
    age_features =[]
    age_whitelist = [
        'AverageTweetLength'
    ]

    user_age_buckets = []
    age_bucket_features = []
    age_bucket_whitelist = [
        'AverageTweetLength'
    ]

    for user, user_feature in zip(user_list, calculated_features):
        if user.gender == "Male":
            user_genders.append(0)
            gender_features.append(user_feature)
        elif user.gender == "Female":
            user_genders.append(1)
            gender_features.append(user_feature)
        if user.education != None:
            user_educations.append(user.education)
            education_features.append(user_feature)
        if user.year != None:
            user_ages.append(user.year)
            age_features.append(user_feature)
        if user.year != None:
            if user.year < 2015 and user.year >=1988:
                user_age_buckets.append(0)
                age_bucket_features.append(user_feature)
            elif user.year < 1988 and user.year > 1977:
                user_age_buckets.append(1)
                age_bucket_features.append(user_feature)
            elif user.year <= 1977:
                user_age_buckets.append(2)
                age_bucket_features.append(user_feature)

    # Filter out non-whitelist features
    gender_features = _filterFeatures(gender_whitelist, gender_features)
    education_features = _filterFeatures(education_whitelist, education_features)
    age_features = _filterFeatures(age_whitelist, age_features)
    age_bucket_features = _filterFeatures(age_bucket_whitelist, age_bucket_features)

    # Test the accuracy
    _testAccuracy('gender', user_genders, gender_features)
    _testAccuracy('education', user_educations, education_features)
    _testAccuracy('age', user_ages, age_features)
    _testAccuracy('age_buckets', user_age_buckets, age_bucket_features)

if __name__ == '__main__':
    main()
