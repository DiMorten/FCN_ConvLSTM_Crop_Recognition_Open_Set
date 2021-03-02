import os
import json
class Params():
    """Class that loads hyperparameters from a json file.

    Example:
    ```
    params = Params(json_path)
    print(params.learning_rate)
    params.learning_rate = 0.5  # change the value of learning_rate in params
    ```
    """

    def __init__(self, json_path):

        assert os.path.isfile(json_path), "No json configuration file found at {}".format(json_path)
        with open(json_path) as f:
            params = json.load(f)
            self.__dict__.update(params)

    def save(self, json_path):
        with open(json_path, 'w') as f:
            json.dump(self.__dict__, f, indent=4)
            
    def update(self, json_path):
        """Loads parameters from json file"""
        with open(json_path) as f:
            params = json.load(f)
            self.__dict__.update(params)

    @property
    def dict(self):
        """Gives dict-like access to Params instance by `params.dict['learning_rate']"""
        return self.__dict__

class ParamsTrain(Params):
    def __init__(self, folder_path):
        #json_path = 'parameters/parameters_openset.json'
        #json_path = 'parameters/parameters_closedset_groupclasses.json'
        json_path = folder_path+'parameters_openset_specifyunknownclasses.json'
        json_path = folder_path+'save_nonaugmented_train_patches_unknownclasses.json'

#        json_path = folder_path+'parameters_openset_lessclass8.json'
        json_path = folder_path+'save_nonaugmented_train_patches_lessclass8.json'



        print(os.listdir(folder_path))
        super().__init__(json_path)

class ParamsAnalysis(Params):
    def __init__(self, folder_path):

        json_path = folder_path+'parameters_analysis_closedset.json'

        print(os.listdir(folder_path))
        super().__init__(json_path)