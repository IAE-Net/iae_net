"""
@author: Yong Zheng Ong
loads the dataset
"""
from numpy.lib.npyio import load
import torch
import numpy as np
import scipy.io
import scipy.interpolate as interpolate
import h5py

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

class DataEncapsulator():
    """
    a class to manage dataset loading
    """
    def __init__(self,
                 file_path=None,
                 to_torch=True,
                 to_cuda=False,
                 to_float=True,
                 **_
        ):
        # set default filepath to fno burgers data
        self.file_path = file_path
        if file_path is None:
            self.file_path = "datasets/burgers/data/burgers_data_g2.5_t5_v0.1.mat"

        self.to_torch = to_torch
        self.to_cuda = to_cuda
        self.to_float = to_float

        self.data = None
        self.old_mat = None
        self._load_file()

    def _load_file(self):
        try:
            self.data = scipy.io.loadmat(self.file_path)
            self.old_mat = True
        except:
            self.data = h5py.File(self.file_path)
            self.old_mat = False

    def read_field(self, field):
        x = self.data[field]

        if not self.old_mat:
            x = x[()]
            x = np.transpose(x, axes=range(len(x.shape) - 1, -1, -1))

        print("read field: converting to float...")
        if self.to_float:
            x = x.astype(np.float32)

        print("read field: converting to tensor...")
        if self.to_torch:
            x = torch.from_numpy(x)

            if self.to_cuda:
                print("read field: converting to device...")
                x = x.to(device)

        return x

    def get_sampling_size(self):
        return np.random.choice(self.available_subs)

    def build_data(self, sub=0, target_sub=0, ntrain=10000, ntest=1000, load_type="multi"):
        available_build_types = ["default", "multi", "multi3"]
        if load_type not in available_build_types:
            load_type = "multi"

        # set basic details
        self.ntrain = ntrain
        self.ntest = ntest
        self.ts = target_sub
        self.num_d = 1 # 1 dimension problem
        self.input_channel = 2 # (a(x), x)
        self.output_channel = 1 # (u(x))
        self.load_type = load_type
        self.available_subs = [2**0, 2**1, 2**2, 2**3, 2**4, 2**5]

        # set max size data - this is the maximum size of the data to be used
        self.max_sub = 2**0
        self.max_s = 2**13 // self.max_sub # total grid size divided by the subsampling rate

        # set data original size = this is the original size of the data
        self.sub = 2**sub
        self.s = 2**13 // self.sub #total grid size divided by the subsampling rate

        # set target data size = this is the target data size
        self.target_sub = 2**target_sub
        self.target_s = 2**13 // self.target_sub

        # load the main data
        x_data = self.read_field('a')[:,::self.max_sub]
        y_data = self.read_field('u')[:,::self.max_sub]

        # interpolate data
        x_range = np.linspace(0, 1, self.s) # get a range of values for interpolations
        x_range_new = np.linspace(0, 1, self.max_s) # get a range of values for interpolations
        x_data = torch.from_numpy(interpolate.interp1d(x_range, x_data.numpy(), kind='cubic')(x_range_new).astype(np.float32))
        y_data = torch.from_numpy(interpolate.interp1d(x_range, y_data.numpy(), kind='cubic')(x_range_new).astype(np.float32))

        # normalize the data
        x_data = (x_data - torch.mean(x_data)) / torch.std(x_data)
        y_data = (y_data - torch.mean(y_data)) / torch.std(y_data)

        # build train and test data
        # case number 1 - x_train is of grid size self.s, x_test is of grid size self.target_s
        if self.load_type == "default":
            print("building data for case = 1: x_train is of grid size self.s, x_test is of all the grid sizes")
            self.x_train = x_data[:self.ntrain,::self.sub]
            self.x_test = x_data[-self.ntest:,::self.max_sub]

            self.y_train = y_data[:self.ntrain,::self.sub]
            self.y_test = y_data[-self.ntest:,::self.max_sub]

            # build the locations information
            grid_train = np.linspace(0, 2*np.pi, self.s).reshape(1, self.s, 1)
            grid_train = torch.tensor(grid_train, dtype=torch.float)

            grid_test = np.linspace(0, 2*np.pi, self.max_s).reshape(1, self.max_s, 1)
            grid_test = torch.tensor(grid_test, dtype=torch.float)

            # concatenate grid to x data
            self.x_train = torch.cat([self.x_train.reshape(self.ntrain,self.s,1), grid_train.repeat(self.ntrain,1,1)], dim=2)
            self.x_test = torch.cat([self.x_test.reshape(self.ntest,self.max_s,1), grid_test.repeat(self.ntest,1,1)], dim=2)

            print("training shape: x - {}, y - {}".format(self.x_train[0].numpy().shape, self.y_train[0].numpy().shape))
            print("testing shape: x - {}, y - {}".format(self.x_test[0].numpy().shape, self.y_test[0].numpy().shape))

        if self.load_type == "multi":
            print("building data for case = 2: x_train is of all the grid sizes, x_test is of all the grid sizes")
            self.x_train = x_data[:self.ntrain,::self.max_sub]
            self.x_test = x_data[-self.ntest:,::self.max_sub]

            self.y_train = y_data[:self.ntrain,::self.max_sub]
            self.y_test = y_data[-self.ntest:,::self.max_sub]

            # build the locations information
            grid_train = np.linspace(0, 2*np.pi, self.max_s).reshape(1, self.max_s, 1)
            grid_train = torch.tensor(grid_train, dtype=torch.float)

            grid_test = np.linspace(0, 2*np.pi, self.max_s).reshape(1, self.max_s, 1)
            grid_test = torch.tensor(grid_test, dtype=torch.float)

            # concatenate grid to x data
            self.x_train = torch.cat([self.x_train.reshape(self.ntrain,self.max_s,1), grid_train.repeat(self.ntrain,1,1)], dim=2)
            self.x_test = torch.cat([self.x_test.reshape(self.ntest,self.max_s,1), grid_test.repeat(self.ntest,1,1)], dim=2)

            print("training shape: x - {}, y - {}".format(self.x_train[0].numpy().shape, self.y_train[0].numpy().shape))
            print("testing shape: x - {}, y - {}".format(self.x_test[0].numpy().shape, self.y_test[0].numpy().shape))

        if self.load_type == "multi3":
            raise NotImplementedError("multi3 is not implemented for burgers dataset yet!")

        # to be cleaned
        self.y_test_mask = None
