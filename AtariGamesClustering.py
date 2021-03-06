import pandas as pd
import numpy as np
import scoreVisualisation
import os
import random
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn_extra.cluster import KMedoids
from sklearn.metrics import jaccard_score
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
import matplotlib.pyplot as plt
import time
import warnings
import webbrowser
from sklearn.utils._testing import ignore_warnings
from sklearn.exceptions import ConvergenceWarning


class AtariGamesClustering:
    """A class for Atari Games clustering methods. The csv should have for every game a single row, with features 
    as columns
    Args:
        dataPath (filePath): [A path to a csv file with data to cluster with]
    """

    def __init__(self, dataPath):
        """ Constructor

        Args:
            dataPath (filePath): [path to CSV-File, used as data]
            saveFileName ([type]): [filename to save work in]
        """

        #CAREEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE!
        warnings.simplefilter(action="ignore", category=FutureWarning)
        warnings.simplefilter(action="ignore", category=UserWarning)
        self.dataFile = None
        self.info = []
        self.numberCategorizations = 0
        self.numberFeatureSelections = 0
        self.DBSCANEpsilon = None
        self.needEpsilon = True
        self.AlgoType = None
        self.NormType = None
        self.AlongGame = None
        self.metric = "euclidean"

        #scoring weights 
        self.mss = 0.50
        self.rs = 0.45 
        self.ins = 0.05


        #first set info of possible normalization types and 
        self.normalizationTypes: list = self.__setNormalizationTypes()
        self.categorizationAlgos: list = self.__setCatAlgos()

        #prepare data to numpy array
        self.listOfGameNames, self.originalData, self.listOfFeatureNames = self.__prepData(dataPath)

        self.data = np.copy(self.originalData)

    def setClusterAlgorithm(self, methodName):
        """Sets the cluster Algorithm, needs to be called before calling Clustering(...) method

        Args:
            methodName (String): [Methodname of clustering, valid: {"KMeans", "KMedoids", "GMM", "DBSCAN"}]
        """
        self.__checkCategMethodVal(methodName)
        self.AlgoType = methodName

    def getClusterAlgorithm(self):
        algo = self.AlgoType
        if algo is None:
            raise ValueError("Please make sure that you have set the Clustering Algorithm with setClusterAlgorithm(...)")
        else:
            return algo

    
    def setNormalization(self, normType, alongGame):
        """Sets the type of normalization for use in Methods which normalize data:
        Clustering, optimalParamClustering, etc..

        Args:
            normType (String): [Normalization type. Valid: {"Min-Max", "Standard", "NoNorm"}]
            alongGame (Bool): [Whether to normalize sample-wise or feature-wise]
        """
        self.__checkNormVal(normType)
        self.NormType = normType
        self.AlongGame = alongGame

    def getNormalization(self):
        normalization = (self.NormType, self.AlongGame)
        if normalization is None:
            raise ValueError("Please make sure that you have set the Normalization type with setNormalization(...)")
        if normalization[0] is None or normalization[1] is None:
            raise ValueError("Please make sure that you have set the Normalization type with setNormalization(...)")
        else:
            return normalization

    def __checkFileCompatibility(self, baselineCSV):
        """Checks compatibility of original data file and baseline file. If data isn't in right format to begin with, give warning

        Args:
            baselineCSV (String): [File in ./BaselineNormalizations]

        Returns:
            [Bool]: [If both data files are in valid format, check whether they match]
        """

        warningMessage = lambda file :  f"WARNING! {file} not in desired Format, cannot check baseline compatibility"
        #we can only really check if formats are ok if format was followed 
        if "_" in self.dataFile and "_" in baselineCSV:
            values = self.dataFile.split("_")
            values2 = baselineCSV.split("_")
            if len(values) != 2 or len(values2) != 3:
                if len(values) != 2:
                    warningMessage(values)
                else:
                    warningMessage(values2)
                return True
            else:
                datatype1 = values[0]
                datatype2 = values2[0]

                eval1 = values[1]
                eval2 = values2[2]
                if (datatype1 != datatype2) or (eval1 != eval2):
                    print("Baseline and original Data aren't of same types, please check validity of data")
                    return False
                else:
                    return True
        else:
            orgOk = "_" in self.dataFile
            if orgOk:
                warningMessage(baselineCSV)
            else:
                warningMessage(self.dataFile)
            return True

    def convertDRLScores(self, baselineCSV, startIndexes=None, endIndexes = None):
        """Converts Raw DRL-Scores contained in the original data to normalized data (human-normalized for example)

        Args:
            normalizationCSVPath (String): [A csv file in ./BaselineData]
            startIndexes (List, defaults to None): [List of start indexes. Every start index indicates the first column of DRL-Agent scores of some evaluation type to normalize on.
                                                    Minimum possible index is always 1 (since Games are 0). If None, whole data is replaced]
            endIndexes (List, defaults to None): [List of end indexes (! inclusive !). Analogous to start indexes]
        """

        path = f"./BaselineNormalizations/{baselineCSV}.csv"
        isOk = self.__checkFileCompatibility(baselineCSV)

        if not isOk:
            raise ValueError("Baseline CSV and original data CSV don't match")
        #first a lot of checks 
        #check lists 
        indexesAreNone = (startIndexes is None) and (endIndexes is None)
        if not indexesAreNone:
            if (not isinstance(startIndexes, list)) or (not isinstance(endIndexes, list)):
                raise TypeError("Indexes need to be lists")
            #inform user about feature range
            print("-------------------------------------")
            print("Features to be changed are")
            for i in range(len(startIndexes)):
                print(f"From {self.listOfFeatureNames[startIndexes[i]]} to {self.listOfFeatureNames[endIndexes[i]]}")
            print("Is this right? enter [y] or [n]")
            yOrN = input("")
            while "y" not in yOrN and "n" not in yOrN:
                print("Input is invalid, please reenter:")
                yOrN = input("")
            if "n" in yOrN:
                raise ValueError("Please modify the indexes and start the program again")

                
            

        if not indexesAreNone:
            #check matching list sizes 
            if len(startIndexes) != len(endIndexes):
                raise ValueError("Lists don't match")


        baselineFrame = pd.read_csv(path)
        #check that size is right for data 
        indexSize = len(baselineFrame.columns)
        
        #2*listSize + 1 because CSV contains column with game names
        #for simple case simply == 3 
        if indexSize != 3:
            if not indexesAreNone and indexSize != 2*len(startIndexes)+1:
                raise ValueError("CSV isn't in right format or indexes are wrong")


        baselineData = baselineFrame.iloc[:, 1:].to_numpy()



        #number baselines and random agent scores
        #first check that number cols is correct
        sizeBaseline = baselineData.shape[1]
        if sizeBaseline % 2 != 0:
            raise ValueError("Format incorrect: Columns need to be [Baseline1, Randomscore1, (Baseline2, Randomscore2, ...)]")


        baselineInfo = f"Scores were normalized with data from {path}"
        #we only need to check if we have complex baseline normalization (more than a single one)
        needCheck = (startIndexes is not None) and endIndexes is not None
        #if we dont need a check stuff gets easier
        if not needCheck:
            baseScore = baselineData[:, 0].reshape(-1, 1)
            randomScore = baselineData[:, 1].reshape(-1, 1)

            data = self.getData()
            newData = (data - randomScore) / (baseScore - randomScore)
            self.__setData(newData)
            self.__addInfo(baselineInfo)
            return

        baselineScores = np.zeros((baselineData.shape[0], int(sizeBaseline / 2)))
        randomScores = np.zeros((baselineData.shape[0], int(sizeBaseline / 2)))

        for i in range(int(sizeBaseline/2)):
            baselineScores[:, i] = baselineData[:, i]
            randomScores[:, i] = baselineData[:, i+1]

        data = self.getData()
        #now normalize original data

        sizeListIndexes = len(startIndexes)

        for i in range(sizeListIndexes):
            startIndex = startIndexes[i]
            endIndex = endIndexes[i]

            currRandomScore = randomScores[:, i].reshape(-1, 1)
            currBaselineScore = baselineScores[:, i].reshape(-1, 1)

            currData = data[:, startIndex:endIndex+1]
            newData = (currData - currRandomScore) / (currBaselineScore - currRandomScore)
            self.__setData(newData, startIndex, endIndex)
            self.__addInfo(baselineInfo)

    
    def __normalizeData(self, dataToNormalize, writeInfo=False):
        """Normalizes data. setNormalization(...) should be called beforehand (!)

        Args:
            dataToNormalize ((g,f) numpy-Array): [The data to normalize: g games and for every game f features]
            writeInfo (Boolean, Defaults to False): [Whether to add info or not]
        Returns:
            normalizedData ((g,f) numpy-Array): [Normalized data]
        """

        normMethod, alongGame = self.getNormalization()
        self.__checkNormVal(normMethod)


        #if we have alongInformation scaling and number of rows == 1 -> can't normalize
        if not alongGame and dataToNormalize.shape[0] == 1:
            return dataToNormalize


        #if we want to do stuff along the game, transpose data
        if alongGame:
            #if #columns == 1 we cant do normalization along games, so just return value
            if dataToNormalize.shape[1] == 1:
                return dataToNormalize
            dataToNormalize = np.transpose(dataToNormalize)
        
        normMethodInfo = f"Normalization was done with Method: {normMethod}"
        if normMethod == "Min-Max":
            #min-max only makes sense with at least 3 samples
            if dataToNormalize.shape[0] < 3:
                normMethodInfo = f"Normalization was done using NoNorm"
                normalizedData = dataToNormalize
            else:
                maxPerformances = np.max(dataToNormalize, axis=0)
                minPerformances = np.min(dataToNormalize, axis=0) 
                normalizedData = (dataToNormalize - minPerformances)/ (maxPerformances - minPerformances)
        elif normMethod == "Standard":
            #check if number samples is atleast bigger than two, else it doesn't really give plausible data 
            if dataToNormalize.shape[0] < 3:
                normMethodInfo = f"Normalization was done using NoNorm"
                normalizedData = dataToNormalize
            else:
                scaler = StandardScaler()
                normalizedData = scaler.fit_transform(dataToNormalize)
        elif normMethod == "NoNorm":
            normalizedData = dataToNormalize


        #add info of methods used to information
        if writeInfo:
            alongGameInfo = f"Normalization was done along games: {alongGame}"
            self.__addInfo(alongGameInfo)
            self.__addInfo(normMethodInfo)
        
        #if we wanted alongGame we transposed data before, so undo that
        if alongGame:
            normalizedData = np.transpose(normalizedData)

        return normalizedData

    def resetData(self):
        """Resets the data to the original data from the input CSV

        Returns:
            [(g,n) numpy-Array]: [Numpy Array containing the original data of the csv]
        """
        return np.copy(self.originalData)


    def __getListOfGames(self):
        """Returns list of game names present in original CSV

        Returns:
            [LIst]: [Game names]
        """
        return self.listOfGameNames

    def __getInfo(self):
        """Returns the info written from methods

        Returns:
            [String]: [Current Info]
        """
        return self.info

    def __getFeatureNames(self):
        return self.listOfFeatureNames


    def getData(self):
        """Returns current data (changed by convertDRLScores)

        Returns:
            [(g,m) Numpy-Array]: [Current data]
        """
        return np.copy(self.data)

    def __setData(self, data, startIndex=0, endIndex=-1):
        """Sets the original data to the input data at the specified indexes

        Args:
            data ((g,f) numpy-Array): [Data to override with]
            startIndex (int, optional): [Start index of overwriting]. Defaults to 0.
            endIndex (int, optional): [End index of overwriting]. Defaults to -1.
        """



        #check that indexes aren't weird
        if (startIndex >= endIndex and endIndex != -1) or startIndex < 0 or endIndex > self.data.shape[1]:
            raise ValueError("Either start index or end index is non valid")
        #check that size of data and indexes match 
        if endIndex != -1:
            if data.shape != self.data[:, startIndex:endIndex+1].shape:
                raise ValueError("Non matching sizes")

        #make index inclusive not exclusive
        if endIndex != -1:
            endIndex += 1

        if endIndex == -1 and startIndex == 0:
            self.data = np.copy(data)
        else:
            self.data[:, startIndex:endIndex] = data


    def makeFileName(self):
        """[creates corresponding Filename that should be used to save, depending on normalization, clustering method etc]

        Returns:
            [String]: [Name of file]
        """
        clusterDataName = self.dataFile
        norm = self.getNormalization()
        cluster = self.getClusterAlgorithm()

        along = None
        if norm[1]:
            along = "AlongGame"
        else:
            along = "AlongInfo"

        fileName = f"{clusterDataName}_{cluster}_{along}"
        return fileName


    def calculateBestAlgorithm(self, data, useSFS=False, useDBSCAN=False, writeInfo=False):
        """Calculates the best Algorithm, regarding scoring measures. Be aware that this sets normalization and clustering algorithm!

        Args:
            data [(g,m) numpy-Array]: [Data used to calculate the best clustering. Must be non-normalized (!)]
            useSFS (bool, optional): [Whether to use Sequential Feature Selection while calculating best Algorithm]. Defaults to False.
            useDBSCAN (bool, optinal): [Whether to include DBSCAN in the algorithm to use. Will procude additional overhead as Elbow-Method will be needed]
            writeInfo (bool, optional): [Whether to write info of the best cluster Algorithm]. Defaults to False.

        Returns:
            [(g,) numpy-Array]: [Labels of the resulting best clustering]
        """

        if useDBSCAN:
            print("----------------------------------------------------------------------------------------")
            print("ATTENTION!   ATTENTION!  ATTENTION!  ATTENTION!  ATTENTION!  ATTENTION!  ATTENTION!")
            print("YOU ENABLED DBSCAN, THEREFORE YOU WILL NEED TO CALCULATE MANY HYPERPARAMETERS WITH ELBOW")
            print("----------------------------------------------------------------------------------------")
            time.sleep(5)


        progress = 0 
        possibleAlgorithms = len(self.getPossibleCatAlgorithms())
        if not useDBSCAN:
            possibleAlgorithms -= 1

        normPossibilities = 0
        for norm in self.getPossibleNormalizations():
            if norm == "NoNorm":
                normPossibilities += 1
            else:
                normPossibilities += 2
        maxProgress = possibleAlgorithms * normPossibilities
        bestNorm = None
        bestClusterAlgo = None
        bestClusterParam = None
        finalData = None
        if useSFS:
            bestFeatures = None
        bestScore = -np.inf



        #iterate over all possibilities 
        for clusterAlgo in self.getPossibleCatAlgorithms():
            print(self.getPossibleCatAlgorithms())
            if (clusterAlgo == "DBSCAN" and not useDBSCAN):
                continue
            self.setClusterAlgorithm(clusterAlgo)
            for norm in self.getPossibleNormalizations():
                for alongGame in [True, False]:
                    #save uneccessary computations
                    if norm == "NoNorm" and alongGame == False:
                        continue
                    startData = np.copy(data)
                    self.setNormalization(norm, alongGame)
                    try:
                        if useSFS:
                            selectedData, features = self.__sfsSelection(startData, self.listOfFeatureNames, toKeep=8)
                        else:
                            selectedData = np.copy(startData)
                        clusterParam = self.optimalClusterParam(selectedData)
                        labels, _ = self.cluster(selectedData, clusterParam)
                        currentScore = self.calcScore(selectedData, labels, clusterParam)
                    except(ValueError):
                        #if normalization error somewhere, we set score of current clustering to -np.inf
                        currentScore = -np.inf


                    #check if score is better than current best
                    if currentScore > bestScore:
                        finalData = selectedData
                        bestFeatures = features
                        bestScore = currentScore
                        bestNorm = (norm, alongGame)
                        bestClusterAlgo = clusterAlgo
                        bestClusterParam = clusterParam
                    progress +=1 
                    print(f"Best Algorithm calculation done: {100*float(progress/maxProgress)}%")

        #calculate clustering 
        self.setNormalization(bestNorm[0], bestNorm[1])
        self.setClusterAlgorithm(bestClusterAlgo)
        bestAlgoInfo = f"Best Algorithm calculation"
        if writeInfo:
            normUsed = f"Normalization used was {bestNorm[0]}; AlongGame: {bestNorm[1]}"
            self.__addInfo(normUsed)
            if useSFS:
                featureInfo = f"Features kept are: {bestFeatures}" 
                self.__addInfo(featureInfo)
            self.__addInfo(bestAlgoInfo)
        labels, _ = self.cluster(finalData, hyperParam=bestClusterParam, writeInfo=writeInfo)
        print(self.getScoringWeights())
        finalScore = self.calcScore(finalData, labels, bestClusterParam, writeInfo=writeInfo)
        finalScoreInfo = f"Final score of your clustering is: {finalScore}"
        if writeInfo:
            self.__addInfo(finalScoreInfo)
        return labels, finalData


    def __checkPath(self, fileName, ending):

        folder = None
        if ending == "png":
            folder = "Visualisations"
        elif ending == "txt":
            folder = "CategInfo"
        elif ending == "html":
            folder = "Heatmaps"
        elif ending == "csv":
            folder = "CalculatedCats"
        else:
            raise ValueError("This type of file is not supported")


        counter = 0
        alreadyExists = os.path.isfile(fileName)
        path = f"./{folder}/{fileName}.{ending}"
        while alreadyExists:
            counter += 1
            path = f"./{folder}/{fileName}{counter}.{ending}"
            alreadyExists = os.path.isfile(fileName)
        return path


    def writeInfo(self, fileName):
        """[Write the categorization info into CategInfo/fileName]]

        Args:
            fileName (String): [Name of output .txt file]
        """

        path = self.__checkPath(fileName, "txt")

        info = self.__getInfo()
        f = open(path, "w")
        for infoString in info:
            if not infoString.isspace():
                f.write(f"{infoString}\n")
        f.close()


    def saveClustering(self, labels, saveFileName):
        """Saves a Clustering under CalculatedCats with the name specified

        Args:
            labels ((g,) numpy-Array): [1d numpy-Array containing the calculated clusters]
            saveFileName (String): [The name to save the csv under in CalculatedCats]
        """
        gameNames = self.__getListOfGames()
        if labels.size != gameNames.size:
            raise ValueError("The calculated labels doesn't match the number of games of the original data")

        csvData = {'Game': gameNames, 'Categories': labels}
        dataFrame = pd.DataFrame(data=csvData)
        path = self.__checkPath(saveFileName, "csv")
        dataFrame.to_csv(path, index=False)

    
    def heatmap(self, labels, saveFileName):
        """Saves a Heatmap. 
        The data is the original data without feature selection

        Args:
            labels ((g,) numpy-Array): [1d numpy-Array containing the calculated clusters]
            saveFileName (String, Defaults to None): [Filename to save Heatmap, under ./Heatmaps./saveFileName]
        """

        #first make csv containing games, original data, categories

        #(g,f) numpy array
        data = self.originalData

        #convert data to appropriate format for heatmap 
        #set normalization to min-max, alonGame, keep old normalization for afterwards
        currentNorm = self.getNormalization()
        self.setNormalization("Min-Max", True)
        data = self.__normalizeData(data)

        games = self.listOfGameNames
        featureNames = self.listOfFeatureNames

        #build dataframe
        startData = {'Game': games}
        startIndex = 1
        dataFrame = pd.DataFrame(data=startData)

        #insert featureNames
        for i in range(featureNames.size):
            dataFrame.insert(startIndex, featureNames[i], data[:, i])
            startIndex += 1 

        #insert labels
        dataFrame.insert(startIndex, "Categories", labels, allow_duplicates=True)

        #convert to csv needed for heatmap 
        heatmap = scoreVisualisation.catVis(dataFrame, False, False)

        newPath = self.__checkPath(saveFileName, "html")
        heatmap.save(newPath)
        webbrowser.open(newPath)

        

        self.setNormalization(currentNorm[0], currentNorm[1])






    def __checkCategMethodVal(self, categMethod):
        if categMethod not in self.getPossibleCatAlgorithms() and categMethod is not None:
            raise ValueError(f"Clustering Algorithm {categMethod} is not specified, possible Values are: {self.getPossibleCatAlgorithms()}")
    
    def __checkNormVal(self, normMethod):
        if normMethod not in self.getPossibleNormalizations() and normMethod is not None:
            raise ValueError(f"This type of Normalization {normMethod} is not supported, supported is: {self.getPossibleNormalizations()}")

    def optimalClusterParam(self, data, writeInfo = False):
        """Calculates optimal hyperparameter of the corresponding Cluster Algorithm set currently. For DBSCAN -> epsilon (int) by Elbow Method. For others -> k (int) by weighted Mean Silhouette Coefficient

        Args:
            data ((g,f) numpy-Array): [The data used to cluster games]
            writeInfo (Bool, defaults to False): [Whether to write info in later info file]

        Returns:
            param (Value): [k for all Algorithms except DBSCAN. epsilon for DBSCAN]
        """

        #if dbscan, we just need DBSCAN-Elbow
        if self.getClusterAlgorithm() == "DBSCAN":
            return self.__DBSCANElbow(data)

        silhouetteScores = list()

        upperBound = int(data.shape[0] / 2)
        lowerBound = 4
        for i in range(lowerBound, upperBound):
            _, currScore = self.cluster(data, i)
            silhouetteScores.append(currScore)
        
        silhouetteScores = np.array(silhouetteScores).squeeze()
        #get best N (we assume ascending sorting)
        #+2 because we start with k=4
        bestN = np.argsort(silhouetteScores)[::-1] + lowerBound
        bestN = bestN[:5]
        bestNScores = np.take(silhouetteScores, bestN-lowerBound)
        #we do own scoring, because having more categories is better but we penalize with score 
        bestNPenalized = (75*bestNScores)/100 + (25*(bestN / np.max(bestN)))/100

        n = bestN[np.argmax(bestNPenalized)]
        correspondingScore = bestNScores[np.argmax(bestNPenalized)]
        startStringInfo = "Silhouette Component Info:"
        silhouetteInfo = f"Weighted Silhouette scoring proposes: {bestN}, with best k = {n} and corresponding score is {correspondingScore}"
        if writeInfo:
            self.__addInfo(startStringInfo)
            self.__addInfo(silhouetteInfo)
        if self.getClusterAlgorithm() == "DBSCAN":
            print(n)
        if n == 1: 
            raise ValueError("HOW THE FUCK DID THIS HAPPEN DUDE")
        return n


    def __setMetric(self, method):
        self.metric = method

    def __getMetric(self):
        return self.metric

    @ignore_warnings(category=ConvergenceWarning)
    def cluster(self, data, hyperParam, writeInfo=False):
        """Clusters normedData by the specified clustering method

        Args:
            data ((g,f) numpy-Array): [Feature Matrix of data for g games]
            hyperParam (Value): [Number of clusters to use for all Algorithms except DBSCAN. For DBSCAN epsilon]
            writeInfo (Boolean): [Whether to add information to later information file]
        Returns:
            labels ((g,) numpy-Array): [Labels for the data]
            score (Float): [Mean silhouette coefficient of the clustering]
        """
        self.numberCategorizations += 1
        normedData = self.__normalizeData(data)
        catMethod = self.getClusterAlgorithm()

        if writeInfo:
            infoStart = "Clustering Info:"
            infoString = f"Categorization was done with {catMethod}, with hyperparameter: {hyperParam}"
            self.__addInfo(infoStart)
            self.__addInfo(infoString)

        metric = "euclidean"
        if catMethod == "KMeans":
            n = int(hyperParam)
            model = KMeans(n)
        elif catMethod == "GMM":
            n = int(hyperParam)
            model = GaussianMixture(n, random_state=0, covariance_type="tied")
        elif catMethod == "KMedoids_Cos":
            n = int(hyperParam)
            metric = "cosine"
            model = KMedoids(n, metric=metric)
        elif catMethod == "KMedoids_Man":
            n = int(hyperParam)
            metric = "manhattan"
            model = KMedoids(n, metric=metric)
        elif catMethod == "DBSCAN":
            model = self.__DBSCANAlgo(normedData, epsilon = hyperParam, writeInfo=writeInfo)
        else: 
            raise ValueError("Categorization algorithm not known")
        
        labels = model.fit_predict(normedData)

        self.__setMetric(metric)

        #if #labels == 1 -> score is -1, because we have no information from clustering 
        if np.unique(labels).size == 1:
            score = 0
        elif catMethod != "DBSCAN" and np.unique(labels).size != hyperParam:
            score = 0
        else:
            score = self.__silhouette_score(normedData, labels, metric)
        return labels, score

    def getPossibleFeatureMethods(self):
        return ["pca", "pearson"]

    def visualize(self, labels, data, fileName=None):
        """1D/2D Visualisation of clustering

        Args:
            labels ((g,) numpy-Array): [Labels of clustering]
            data ((g,m) numpy-Array): [Data to visualize on]
            fileName (String): [Filename to save visualisation under ./Visualisations. If None, vis is not saved]
        """

        normedData = self.__normalizeData(data)
        #check if #samples match 
        if labels.size != normedData.shape[0]:
            raise ValueError("Mismatch between labels and data")
    
        currData = np.copy(normedData)
        #pca of data to 2D
        if currData.shape[1] > 2:
            visPCA = PCA(n_components=2)
            currData = visPCA.fit_transform(currData)
        if currData.shape[1] == 1:
            y = np.zeros((currData.shape)).squeeze()
            x = currData.squeeze()
            y[:] = 5
        else:
            x = currData[:, 0].squeeze()
            y = currData[:, 1].squeeze()
        for cat in np.unique(labels):
            plt.scatter(x[labels == cat], y[labels == cat], label=cat)
            #annotate points with names
        for i in range(len(self.listOfGameNames)):
            plt.annotate(self.listOfGameNames[i], (x[i], y[i]))
        plt.legend()

        #save plt if wanted 
        if fileName is not None:
            newPath = self.__checkPath(fileName, "png")

            plt.savefig(newPath)

        plt.show()





    def featureEngineerer(self, data, method="pearson", writeInfo=False):
        """Calculates feature selected data from the input data.


        Args:
            data ((g,m)): [Data to feature engineer on. Doesn't support consecutive feature engineering on same data!]
            method (string): [Method to use when doing feature selection]

        Returns:
            data ((g,m')): [Feature Engineered data]
        """
        features = np.copy(data)
        featureNames = self.__getFeatureNames()

        #check if featureNames alignes with data features
        if featureNames.size != features.shape[1]:
            raise ValueError("Cannot feature engineer data. Have you already applied feature engineering on this data? then reset your data!")


        featureEngInfo = f"Feature Engineering with {method}"
        if writeInfo:
            self.__addInfo(featureEngInfo)
        if method == "pca":
            featureSelector = PCA(n_components=0.95, svd_solver="full")
            featureSelected = featureSelector.fit_transform(features)
            leftFeatures = f"Features still left are {featureNames}"
            if writeInfo:
                self.__addInfo(leftFeatures)
            return np.copy(featureSelected)
        elif method == "pearson":
            dataframe = pd.DataFrame(data=features, columns=featureNames)
            correlation = np.abs(dataframe.corr(method="pearson").to_numpy())

            #feature indexes to remove
            indexes = list()

            #remove features with correlation > 0.9
            for i in range(correlation.shape[0]):
                for j in range(correlation.shape[1]):
                    if j in indexes:
                        continue 
                    #if same index we have 1 and pass
                    if i == j:
                        continue
                    if correlation[i][j] > 0.9:
                        #i throw away myself
                        indexes.append(i)
            indexes = np.unique(np.array(indexes))
        
            #drop data that we dont need anymore
            newFeatures = np.delete(features, indexes, axis=1)
            newFeatureNames = np.delete(featureNames, indexes, axis=0)
            leftFeatures = f"Features still left: {newFeatureNames}"
            if writeInfo:
                self.__addInfo(leftFeatures)
            #not with setData() because we override the original data!
            return np.copy(newFeatures)
        else:
            raise ValueError(f"{method} as Method for feature selection not known")


    def setScoringWeights(self, weightTuple):
        self.mss = weightTuple[0]
        self.rs = weightTuple[1] 
        self.ins = weightTuple[2]

    def getScoringWeights(self):
        return (self.mss, self.rs, self.ins)


    def __sfsSelection(self, data, featureNames, toKeep=5):
        """Feature Selection with Sequential Forward Selection

        Args:
            data ((g,f) numpy-Array): [Numpy Array containing the data]
            featureNames ((f,) numpy-Array): [Array containing the names of the features]
            toKeep (Int): [Number of Features to keep, defaults to 5]

        Returns:
            newData ((g,toKeep)): [Numpy array containing new features]
            features ((toKeep,)): [Features to keep]
        """


        #keep count of optimal features to keep
        indicesToKeep = []
        bestScoreAll = -np.inf
        iterations = 0


        endWeights = self.getScoringWeights()
        tmp = (0.85, 0.075, 0.075)
        self.setScoringWeights(tmp)
        while len(indicesToKeep) < toKeep and iterations != toKeep:
            #ugly but needed: for DBSCAN we set for every iteration epsilon to None because for new features we need new epsilon
            self.__setDBSCANEpsilon(None)


            #every new iteration we keep track of bestScore
            iterations += 1
            bestScore = -np.inf
            indexToKeep = None
            for featureIndex in range(data.shape[1]):
                if featureIndex in indicesToKeep:
                    continue
                currentIndexArray = indicesToKeep + [featureIndex]
                #construct array out of indicestoKeep and current index
                #len == 0 -> just index
                currentData = data[:, currentIndexArray]
                hyperParam = self.optimalClusterParam(currentData)
                labels, _ = self.cluster(currentData, hyperParam=hyperParam)
                score = self.calcScore(currentData, labels, hyperParam, robustIterations=100)
                if score > bestScore:
                    bestScore = score
                    indexToKeep = featureIndex
            if bestScore > bestScoreAll:
                bestScoreAll = bestScore
                indicesToKeep.append(indexToKeep)
            #if the score didn't get better, we already have optimal amount of features
            else:
                iterations = toKeep
                break
    
        self.setScoringWeights(endWeights)
        return data[:, indicesToKeep], featureNames[indicesToKeep]


    def __DBSCANElbow(self, normalizedData):
        """Gives user possibility to get optimal epsilon by Elbow-Method. If not, default-Epsilon is used

        Args:
            data ((g,m) numpy-Array): [Normalized Data to calculate Elbow with]

        Returns:
            [float]: [Epsilon for DBSCAN]
        """


        neighbors = NearestNeighbors(n_neighbors=3)
        nbrs = neighbors.fit(normalizedData)
        distances, _ = nbrs.kneighbors(normalizedData)
        distances = np.sort(distances, axis=0)
        distances = distances[:, 2]
            
        print("Extract from the following plot the elbow-Point for the DBSCAN Algorithm")
        plt.plot(distances)
        plt.show()
        epsilon = input("Please Input the optimal Epsilon obtained by the Elbow-Plot:\n")
        try:
            epsilon = float(epsilon)
        except(ValueError):
            print("Input value was not valid, using default epsilon (probably leads to poor performance")
            epsilon = 0.5
        return epsilon

    def __DBSCANAlgo(self, normalizedData, epsilon = None, writeInfo=False):
        """Calculates the DBSCAN Algorithm. Depending on whether Epsilon is needed, User will set Epsilon by Elbow-Method

        Args:
            normalizedData ((g,m) numpy-Array): [Normalized data to cluster with]
            epsilon ([Float], optional): [Epsilon to use for DBSCAN Algorithm]. Defaults to None.
            writeInfo (bool, optional): [Whether to save used epsilon in config file]. Defaults to False.

        Returns:
            [type]: [description]
        """
        self.__setDBSCANEpsilon(epsilon)
        needElbow = self.__needDBSCANEpsilon()
        if needElbow:
            currEpsilon = self.__DBSCANElbow(normalizedData)
            self.__setDBSCANEpsilon(currEpsilon)
        else:
            if epsilon is not None:
                currEpsilon = epsilon
            currEpsilon = self.__getDBSCANEpsilon()
        

        model = DBSCAN(eps=currEpsilon, min_samples=2)

        if writeInfo:
            info = f"Best epsilon for DBSCAN is {currEpsilon}"
            self.__addInfo(info)
        return model


    def __needDBSCANEpsilon(self):
        return self.__getDBSCANEpsilon() is None

    def __setDBSCANEpsilon(self, epsilon):
        if epsilon is None:
            self.needEpsilon = True
        else:
            self.needEpsilon = False
        self.DBSCANEpsilon = epsilon

    def __getDBSCANEpsilon(self):
        epsilon = self.DBSCANEpsilon

        if epsilon is None:
            raise ValueError("DBSCAN needs Epsilon to continue")

        return epsilon


    def loadClustering(self, fileName):
        """Loads a clustering from a CSV. CSV should have 2 columns: [Games, Labels]

        Args:
            fileName (String): [File in .CalculatedCats/]

        Returns:
            [(g,)]: [Numpy-Array containing the labels of the CSV]
        """

        path = f"./CalculatedCats/{fileName}.csv"
        frame = pd.read_csv(path)
        labels = frame.iloc[:, 1].to_numpy()
        return labels.reshape((-1,1)).squeeze()

    def __silhouette_score(self, data, labels, metric):
        if np.unique(labels).size == 1:
            return 0
        else:
            return (silhouette_score(data, labels, metric)+1)/2

    def calcScore(self, data, labels, clustParam, robustIterations=10000, writeInfo=False):
        """Calculates an Algorithm score from different metrics

        Args:
            data ((g,m) numpy-array): [Unnormalized data to calculate score with]
            labels ((g,) numpy-Array): [Labels of the Clustering]
            clustParam (Cluster Param to cluster with): [Hyperparameter of corresponding cluster algorithm]
            writeInfo (bool, optional): [description]. Defaults to False.

        Returns:
            [Float]: [Score of the clustering algorithm. Best value is 1]
        """

        #if method is not DBSCAN and therefore k != number of clusters in labels -> we have empty labels 
        #=> very bad score 
        if self.getClusterAlgorithm() != "DBSCAN":
            if np.unique(labels).size != clustParam:
                return 0


        normedData = self.__normalizeData(data)
        metric = self.__getMetric()
        score = self.__silhouette_score(normedData, labels, metric=metric)
        robustness = self.calcRobustness(data, clustParam, iterations=robustIterations)
        instanceScore = self.__calcInstanceScore(labels)

        weights = self.getScoringWeights()

        scoreStartInfo = "Scoring:"
        scoreInfo = f"Mean Silhouette Coefficient: {score} (best -> 1), Robustness: {robustness} (best -> 1), InstanceScore: {instanceScore} (best -> 1)"
        if writeInfo:
            self.__addInfo(scoreStartInfo)
            self.__addInfo(scoreInfo)
        finalScore = ((weights[0]*100*score)/100) + ((weights[1]*100*robustness)/100) + ((weights[2]*100*instanceScore)/100)
        return finalScore


    #https://people.eecs.berkeley.edu/~jordan/sail/readings/luxburg_ftml.pdf
    #http://citeseerx.ist.psu.edu/viewdoc/download;jsessionid=9128DE558BAA6F3B88A36718F4FD858D?doi=10.1.1.331.1569&rep=rep1&type=pdf
    #second paper p.6-7
    def calcRobustness(self, data, hyperParam, iterations=1000):
        """Calculates the robustness of a clustering algorithm

        Args:
            data ((g,f) np-array): [The data used for clustering]
            hyperParam (Value): [Hyperparameter used for Clustering]
            categType (String): [type of clustering to use]
        Returns:
            performance (float): [Robustness score of clustering, between [0,1]]
        """


        #we keep 75% information for every iteration
        sampleSize = int(3*data.shape[0]/4)

        #only check if type of clustering is not DBSCAN
        method = self.getClusterAlgorithm()
        if method != "DBSCAN":
            #if number k is greater than samples we have, we cant calculate clustering -> bad clustering
            if hyperParam >= sampleSize:
                return 0
        
        wholeSim = 0
        maxAmount = iterations

        groundTruth, _ = self.cluster(data, hyperParam)

        for _ in range(maxAmount):
            #generate bootstrap sample indices, without replacement for numerical stability
            x_star = random.sample(range(0, data.shape[0]), sampleSize)
            samples = data[x_star, :]
            assert samples.shape[1] == data.shape[1], "sampling on stability testing is wrong"
            compareLabels, _, = self.cluster(samples, hyperParam=hyperParam) 
            #taken from paper
            #indices that were used in the to compare clustering
            #take indices ground truth clustering were indices were used for bootstrapped clustering
            groundTruthCompare = groundTruth[x_star]
            sim = self.__calcSimilarity(groundTruthCompare, compareLabels)
            wholeSim += sim
        
        #calculate average jaccard similarity
        performance = float(wholeSim / maxAmount)

        return performance


    def __calcSimilarity(self, groundTruth, compareValues):
        """
        Calculates jaccard similarity between a ground Truth and calculated clustering. Used for robustness calculation

        Args: 
            groundTruth: (1d-numpy Array): [ground Truth categories]
            compareCats: (1d-numpy Array): [categories to compare]

        Returns: 
            performance: float: performance of the categorization with respect to the constraintMatrix
        """
        return jaccard_score(groundTruth, compareValues, average="weighted")


    def __calcInstanceScore(self, labels):
        """Calculates a goodness of clustering depending on how many games are in the different categories. 
        A good clustering is a clustering with clusters with more than 1 game but not too many games

        Args:
            categories (g numpy-Array): [For each game in the original data the corresponding label]

        Returns:
            [float]: [Instance score]
        """

        #use kl-divergence between uniform distribution and histogram of labels
        uniqueLabels = np.unique(labels)
        numSamples = labels.size

        klDivergence = 0

        #uniform distribution is 1/#cats
        uniform = 1 / uniqueLabels.size

        for cluster in uniqueLabels:
            currentSize = labels[labels == cluster].size
            currentHistogram = currentSize / numSamples

            klDivergence += uniform * np.log(uniform / currentHistogram)
        
        #constraint range to (0,1] and weight by number of samples. Ideally we assume number of categories would be samples / 4

        return np.exp(-klDivergence)



    def __addInfo(self, infoString):
        self.info.append(infoString)

    def __prepData(self, csvPath):
        #set filename of class 
        self.dataFile = csvPath
        dataPath = f"./CatData/{csvPath}.csv"
        self.__addInfo(f"Data used from {dataPath}")

        data = pd.read_csv(dataPath)
        performances = data.iloc[:, 1:].to_numpy()
        perfIndex = data.iloc[:, 1:].columns.to_numpy()
        games = data.iloc[:, 0].to_numpy()
        #convert commas to points for float
        #but only convert if type isn't already float
        isFloat = performances.dtype == float
        if not isFloat:
            convertFloat = lambda x: [s.replace(",", ".") for s in x]
            performances = np.apply_along_axis(convertFloat, 0, performances).astype(float)


        return games, performances, perfIndex


    def __setNormalizationTypes(self):
        normalizationTypes = ["Min-Max", "Standard", "NoNorm"]
        return normalizationTypes

    def __setCatAlgos(self):
        categorizationAlgos = ["KMeans", "KMedoids_Man", "KMedoids_Cos", "GMM", "DBSCAN"]
        return categorizationAlgos


    def getPossibleNormalizations(self):
        return self.normalizationTypes
    
    def getPossibleCatAlgorithms(self):
        return self.categorizationAlgos