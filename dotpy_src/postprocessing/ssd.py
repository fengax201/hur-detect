


import sys
import tensorflow as tf
if __name__ == "__main__":
    sys.path.append("../../")
from dotpy_src.tf_extended import math as tfe_math
from dotpy_src.tf_extended import tensors as tfe_tensors
from dotpy_src.configs import configs
from bboxes import bboxes_sort, bboxes_nms_batch



def detected_bboxes(predictions, localisations,
                        select_threshold=None, nms_threshold=0.5,
                        clipping_bbox=None, top_k=400, keep_top_k=200):
        """Get the detected bounding boxes from the SSD network output by doing nms.
            Returns two dictionares where the keys are the classe indices
            the values for rscores is a num_ex x keep_top_k array of scores for each box
            the vaues for rbboxes is num_ex x keep_top_k x 4 array where each ixjx4 vector is boox_coords for a box
        """
        # Select top_k bboxes from predictions, and clip
        rscores, rbboxes =             tf_ssd_bboxes_select(predictions, localisations,
                                            select_threshold=select_threshold,
                                            num_classes=configs["num_classes"]) #b/c it ignores class 0
        rscores, rbboxes =             bboxes_sort(rscores, rbboxes, top_k=top_k)
        # Apply NMS algorithm.
        rscores, rbboxes =             bboxes_nms_batch(rscores, rbboxes,
                                 nms_threshold=nms_threshold,
                                 keep_top_k=keep_top_k)
        # if clipping_bbox is not None:
        #     rbboxes = tfe.bboxes_clip(clipping_bbox, rbboxes)
        return rscores, rbboxes



def tf_ssd_bboxes_select(predictions_net, localizations_net,
                         select_threshold=None,
                         num_classes=21,
                         ignore_class=0,
                         scope=None):
    """Extract classes, scores and bounding boxes from network output layers.
    Batch-compatible: inputs are supposed to have batch-type shapes.
    Args:
      predictions_net: List of SSD prediction layers;
      localizations_net: List of localization layers;
      select_threshold: Classification threshold for selecting a box. All boxes
        under the threshold are set to 'zero'. If None, no threshold applied.
    Return:
      d_scores, d_bboxes: Dictionary of scores and bboxes Tensors of
        size Batches X N x 1 | 4. Each key corresponding to a class.
    """
    with tf.name_scope(scope, 'ssd_bboxes_select',
                       [predictions_net, localizations_net]):
        l_scores = []
        l_bboxes = []
        for i in range(len(predictions_net)):
            
            scores, bboxes = tf_ssd_bboxes_select_layer(predictions_net[i],
                                                        localizations_net[i],
                                                        select_threshold,
                                                        num_classes,
                                                        ignore_class)
            l_scores.append(scores)
            l_bboxes.append(bboxes)
        # Concat results.
        d_scores = {}
        d_bboxes = {}
        for c in l_scores[0].keys():
            ls = [s[c] for s in l_scores]
            lb = [b[c] for b in l_bboxes]
            d_scores[c] = tf.concat(ls, axis=1)
            d_bboxes[c] = tf.concat(lb, axis=1)
        return d_scores, d_bboxes



def tf_ssd_bboxes_select_layer(predictions_layer, localizations_layer,
                               select_threshold=None,
                               num_classes=21,
                               ignore_class=0,
                               scope=None):
    """Extract classes, scores and bounding boxes from features in one layer.
    Batch-compatible: inputs are supposed to have batch-type shapes.
    Args:
      predictions_layer: A SSD prediction layer;
      localizations_layer: A SSD localization layer;
      select_threshold: Classification threshold for selecting a box. All boxes
        under the threshold are set to 'zero'. If None, no threshold applied.
    Return:
      d_scores, d_bboxes: Dictionary of scores and bboxes Tensors of
        size Batches X N x 1 | 4. Each key corresponding to a class.
    """
    select_threshold = 0.0 if select_threshold is None else select_threshold
    with tf.name_scope(scope, 'ssd_bboxes_select_layer',
                       [predictions_layer, localizations_layer]):
        # Reshape features: Batches x N x N_labels | 4
        p_shape = tfe_tensors.get_shape(predictions_layer)
        predictions_layer = tf.reshape(predictions_layer,
                                       tf.stack([p_shape[0], -1, p_shape[-1]]))
        l_shape = tfe_tensors.get_shape(localizations_layer)
        localizations_layer = tf.reshape(localizations_layer,
                                         tf.stack([l_shape[0], -1, l_shape[-1]]))

        d_scores = {}
        d_bboxes = {}
        for c in range(0, num_classes + 1):
            if c != ignore_class:
                # Remove boxes under the threshold.
                scores = predictions_layer[:, :, c - 1]
                fmask = tf.cast(tf.greater_equal(scores, select_threshold), scores.dtype)
                scores = scores * fmask
                bboxes = localizations_layer * tf.expand_dims(fmask, axis=-1)
                # Append to dictionary.
                d_scores[c] = scores
                d_bboxes[c] = bboxes

        return d_scores, d_bboxes



def tf_ssd_bboxes_select_layer_all_classes(predictions_layer, localizations_layer,
                                           select_threshold=None):
    """Extract classes, scores and bounding boxes from features in one layer.
     Batch-compatible: inputs are supposed to have batch-type shapes.
     Args:
       predictions_layer: A SSD prediction layer;
       localizations_layer: A SSD localization layer;
      select_threshold: Classification threshold for selecting a box. If None,
        select boxes whose classification score is higher than 'no class'.
     Return:
      classes, scores, bboxes: Input Tensors.
     """
    # Reshape features: Batches x N x N_labels | 4
    p_shape = tfe_tensors.get_shape(predictions_layer)
    predictions_layer = tf.reshape(predictions_layer,
                                   tf.stack([p_shape[0], -1, p_shape[-1]]))
    l_shape = tfe_tensors.get_shape(localizations_layer)
    localizations_layer = tf.reshape(localizations_layer,
                                     tf.stack([l_shape[0], -1, l_shape[-1]]))
    # Boxes selection: use threshold or score > no-label criteria.
    if select_threshold is None or select_threshold == 0:
        # Class prediction and scores: assign 0. to 0-class
        classes = tf.argmax(predictions_layer, axis=2)
        scores = tf.reduce_max(predictions_layer, axis=2)
        scores = scores * tf.cast(classes > 0, scores.dtype)
    else:
        sub_predictions = predictions_layer[:, :, 1:]
        classes = tf.argmax(sub_predictions, axis=2) + 1
        scores = tf.reduce_max(sub_predictions, axis=2)
        # Only keep predictions higher than threshold.
        mask = tf.greater(scores, select_threshold)
        classes = classes * tf.cast(mask, classes.dtype)
        scores = scores * tf.cast(mask, scores.dtype)
    # Assume localization layer already decoded.
    bboxes = localizations_layer
    return classes, scores, bboxes



def tf_ssd_bboxes_select_all_classes(predictions_net, localizations_net,
                                     select_threshold=None,
                                     scope=None):
    """Extract classes, scores and bounding boxes from network output layers.
    Batch-compatible: inputs are supposed to have batch-type shapes.
    Args:
      predictions_net: List of SSD prediction layers;
      localizations_net: List of localization layers;
      select_threshold: Classification threshold for selecting a box. If None,
        select boxes whose classification score is higher than 'no class'.
    Return:
      classes, scores, bboxes: Tensors.
    """
    with tf.name_scope(scope, 'ssd_bboxes_select',
                       [predictions_net, localizations_net]):
        l_classes = []
        l_scores = []
        l_bboxes = []
        for i in range(len(predictions_net)):
            classes, scores, bboxes =                 tf_ssd_bboxes_select_layer_all_classes(predictions_net[i],
                                                       localizations_net[i],
                                                       select_threshold)
            l_classes.append(classes)
            l_scores.append(scores)
            l_bboxes.append(bboxes)

        classes = tf.concat(l_classes, axis=1)
        scores = tf.concat(l_scores, axis=1)
        bboxes = tf.concat(l_bboxes, axis=1)
        return classes, scores, bboxes




