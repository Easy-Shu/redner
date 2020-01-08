import tensorflow as tf
import pyredner_tensorflow as pyredner
import math

class Texture:
    """
        Representing a texture and its mipmap.

        Args
        ====
        texels: torch.Tensor
            a float32 tensor with size C or [height, width, C]
        uv_scale: Optional[torch.Tensor]
            scale the uv coordinates when mapping the texture
            a float32 tensor with size 2
    """

    def __init__(self,
                 texels,
                 uv_scale = tf.constant([1.0, 1.0])):
        assert(tf.executing_eagerly())
        self.texels = texels
        self.uv_scale = uv_scale

    def generate_mipmap(self):
        texels = self._texels
        if len(texels.shape) >= 2:
            with tf.device(pyredner.get_device_name()):
                # Build a mipmap for texels
                width = max(texels.shape[0], texels.shape[1])
                num_levels = min(math.ceil(math.log(width, 2) + 1), 8)
                num_channels = texels.shape[2]
                box_filter = tf.ones([2, 2, num_channels, 1], dtype=tf.float32) / 4.0
    
                # HWC -> NHWC
                base_level = tf.expand_dims(texels, axis=0)
    
                mipmap = [base_level]
                prev_lvl = base_level
                for l in range(1, num_levels):
                    # Pad for circular boundary condition
                    # This is slow. The hope is at some point Tensorflow will support
                    # circular boundary condition for conv2d
                    desired_height = prev_lvl.shape[1] + 1
                    while prev_lvl.shape[1] < desired_height:
                        prev_lvl = tf.concat(
                            [
                                prev_lvl, 
                                prev_lvl[:,:,0:(desired_height - prev_lvl.shape[1])]
                            ], 1)
                    desired_width = prev_lvl.shape[2] + 1
                    while prev_lvl.shape[2] < desired_width:
                        prev_lvl = tf.concat(
                            [prev_lvl, prev_lvl[:,:,:,0:1]], 
                            2)
                    # Convolve with a box filter
                    current_lvl = tf.nn.depthwise_conv2d(
                        prev_lvl,
                        box_filter,  # [filter_height, filter_width, in_channels, out_channels]
                        strides=[1,1,1,1],
                        padding="VALID",   # No padding
                        data_format="NHWC"
                    )
                    # Downsample
                    current_lvl = tf.nn.avg_pool(current_lvl, 2)
                    mipmap.append(current_lvl)
                    prev_lvl = current_lvl
    
                texels = mipmap
        self.mipmap = texels

    @property
    def texels(self):
        return self._texels

    @texels.setter
    def texels(self, value):
        self._texels = value
        self.generate_mipmap()

    def state_dict(self):
        return {
            'texels': self.texels,
            'mipmap': self.mipmap,
            'uv_scale': self.uv_scale
        }

    @classmethod
    def load_state_dict(cls, state_dict):
        out = cls.__new__(Texture)
        out.texels = state_dict['texels']
        out.mipmap = state_dict['mipmap']
        out.uv_scale = state_dict['uv_scale'].numpy()
        return out
