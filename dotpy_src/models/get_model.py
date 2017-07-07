


import sys
if __name__ == "__main__":
    sys.path.append("../../")



from dotpy_src.configs import configs
import importlib



from keras.models import Model



model_name = configs["detection_model"]



model_module = importlib.import_module("dotpy_src.models.detection." + model_name)



model_params = model_module.get_model_params()



model = Model(inputs=model_params["inputs"], outputs = model_params["outputs"], name=model_name)



def get_model():
    if "semisupervised" in model_name:
        model.mode = "semi_supervised"
    else:
        model.mode = "supervised"
    return model
