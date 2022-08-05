import torch
from typing import Any, Set, Dict, List, Tuple, OrderedDict
from collections import OrderedDict as OrdDict

# try to import tablate
got_tabulate = True
try:
    from tabulate import tabulate
except ImportError:
    got_tabulate = False


# var to see if we could import matplotlib
got_matplotlib = True
try:
    import matplotlib.pyplot as plt
except ImportError:
    got_matplotlib = False

class ModelReportVisualizer:
    r"""
    The ModelReportVisualizer class aims to provide users a way to visualize some of the statistics
    that were generated by the ModelReport API. However, at a higher level, the class aims to provide
    some level of visualization of statistics to PyTorch in order to make it easier to parse data and
    diagnose any potential issues with data or a specific model. With respect to the visualizations,
    the ModelReportVisualizer class currently supports several methods of visualizing data.

    Supported Visualization Methods Include:
    - Table format
    - Plot format (line graph)
    - Histogram format

    For all of the existing visualization methods, there is the option to filter data based on:
    - A module fqn prefix
    - Feature [required for the plot and histogram]

    * :attr:`generated_reports` The reports generated by the ModelReport class in the structure below
        Ensure sure that features that are the same across different report contain the same name
        Ensure that objects representing the same features are the same type / dimension (where applicable)

    Note:
        Currently, the ModelReportVisualizer class supports visualization of data generated by the
        ModelReport class. However, this structure is extensible and should allow the visualization of
        other information as long as the information is structured in the following general format:

        Report Structure
        -- module_fqn [module with attached detectors]
            |
            -- feature keys [not every detector extracts same information]
                                    [same collected info has same keys, unless can be specific to detector]


    The goal behind the class is that the generated visualizations can be used in conjunction with the generated
    report for people to get a better understanding of issues and what the fix might be. It is also just to provide
    a good visualization platform, since it might be hard to parse through the ModelReport returned dictionary as
    that grows in size.

    General Use Flow Expected
    1.) Initialize ModelReport object with reports of interest by passing in initialized detector objects
    2.) Prepare your model with prepare_fx
    3.) Call model_report.prepare_detailed_calibration on your model to add relavent observers
    4.) Callibrate your model with data
    5.) Call model_report.generate_report on your model to generate report and optionally remove added observers
    6.) Use output of model_report.generate_report to initialize ModelReportVisualizer instance
    7.) Use instance to view different views of data as desired, applying filters as needed
        8.) Either see the super detailed information or just the actual printed or shown table / plot / histogram

    """

    # keys for table dict
    TABLE_TENSOR_KEY = "tensor_level_info"
    TABLE_CHANNEL_KEY = "channel_level_info"

    # Constants for header vals
    NUM_NON_FEATURE_TENSOR_HEADERS = 2
    NUM_NON_FEATURE_CHANNEL_HEADERS = 3

    # Constants for row index in header
    CHANNEL_NUM_INDEX = 2

    def __init__(self, generated_reports: OrderedDict[str, Any]):
        r"""
        Initializes the ModelReportVisualizer instance with the necessary reports.

        Args:
            generated_reports (Dict[str, Any]): The reports generated by the ModelReport class
                can also be a dictionary generated in another manner, as long as format is same
        """
        self.generated_reports = generated_reports

    def get_all_unique_module_fqns(self) -> Set[str]:
        r"""
        The purpose of this method is to provide a user the set of all module_fqns so that if
        they wish to use some of the filtering capabilities of the ModelReportVisualizer class,
        they don't need to manually parse the generated_reports dictionary to get this information.

        Returns all the unique module fqns present in the reports the ModelReportVisualizer
        instance was initialized with.
        """
        # returns the keys of the ordered dict
        return set(self.generated_reports.keys())

    def get_all_unique_feature_names(self, plottable_features_only: bool = True) -> Set[str]:
        r"""
        The purpose of this method is to provide a user the set of all feature names so that if
        they wish to use the filtering capabilities of the generate_table_view(), or use either of
        the generate_plot_view() or generate_histogram_view(), they don't need to manually parse
        the generated_reports dictionary to get this information.

        Args:
            plottable_features_only (bool): True if the user is only looking for plottable features,
                False otherwise
                plottable features are those that are tensor values
                Default: True (only return those feature names that are plottable)

        Returns all the unique module fqns present in the reports the ModelReportVisualizer
        instance was initialized with.
        """
        unique_feature_names = set()
        for module_fqn in self.generated_reports:
            # get dict of the features
            feature_dict: Dict[str, Any] = self.generated_reports[module_fqn]

            # loop through features
            for feature_name in feature_dict:
                # if we need plottable, ensure type of val is tensor
                if not plottable_features_only or type(feature_dict[feature_name]) == torch.Tensor:
                    unique_feature_names.add(feature_name)

        # return our compiled set of unique feature names
        return unique_feature_names

    def _get_filtered_data(self, feature_filter: str, module_fqn_filter: str) -> OrderedDict[str, Any]:
        r"""
        Filters the data and returns it in the same ordered dictionary format so the relavent views can be displayed.

        Args:
            feature_filter (str): The feature filter, if we want to filter the set of data to only include
                a certain set of features that include feature_filter
                If feature = "", then we do not filter based on any features
            module_fqn_filter (str): The filter on prefix for the module fqn. All modules that have fqn with
                this prefix will be included
                If module_fqn_filter = "" we do not filter based on module fqn, and include all modules

        First, the data is filtered based on module_fqn, and then filtered based on feature
        Returns an OrderedDict (sorted in order of model) mapping:
            module_fqns -> feature_names -> values
        """
        # create return dict
        filtered_dict: OrderedDict[str, Any] = OrdDict()

        for module_fqn in self.generated_reports:
            # first filter based on module
            if module_fqn_filter == "" or module_fqn_filter in module_fqn:
                # create entry for module and loop through features
                filtered_dict[module_fqn] = {}
                module_reports = self.generated_reports[module_fqn]
                for feature_name in module_reports:
                    # check if filtering on features and do so if desired
                    if feature_filter == "" or feature_filter in feature_name:
                        filtered_dict[module_fqn][feature_name] = module_reports[feature_name]

        # we have populated the filtered dict, and must return it

        return filtered_dict

    def _generate_tensor_table(
        self,
        filtered_data: OrderedDict[str, Dict[str, Any]],
        tensor_features: List[str]
    ) -> Tuple[List, List]:
        r"""
        Takes in the filtered data and features list and generates the tensor headers and table

        Currently meant to generate the headers and table for both the tensor information.

        Args:
            filtered_data (OrderedDict[str, Dict[str, Any]]): An OrderedDict (sorted in order of model) mapping:
                module_fqns -> feature_names -> values
            tensor_features (List[str]): A list of the tensor level features

        Returns a tuple with:
            A list of the headers of the tensor table
            A list of lists containing the table information row by row
            The 0th index row will contain the headers of the columns
            The rest of the rows will contain data
        """
        # now we compose the tensor information table
        tensor_table: List[List[Any]] = []
        tensor_headers: List[str] = []

        # append the table row to the table only if we have features
        if len(tensor_features) > 0:
            # now we add all the data
            for index, module_fqn in enumerate(filtered_data):
                # we make a new row for the tensor table
                tensor_table_row = [index, module_fqn]
                for feature in tensor_features:
                    # we iterate in same order of added features

                    if feature in filtered_data[module_fqn]:
                        # add value if applicable to module
                        feature_val = filtered_data[module_fqn][feature]
                    else:
                        # add that it is not applicable
                        feature_val = "Not Applicable"

                    # if it's a tensor we want to extract val
                    if isinstance(feature_val, torch.Tensor):
                        feature_val = feature_val.item()

                    # we add to our list of values
                    tensor_table_row.append(feature_val)

                tensor_table.append(tensor_table_row)

        # add row of headers of we actually have something, otherwise just empty
        if len(tensor_table) != 0:
            tensor_headers = ["idx", "layer_fqn"] + tensor_features

        return (tensor_headers, tensor_table)

    def _generate_channels_table(
        self,
        filtered_data: OrderedDict[str, Any],
        channel_features: List[str],
        num_channels: int
    ) -> Tuple[List, List]:
        r"""
        Takes in the filtered data and features list and generates the channels headers and table

        Currently meant to generate the headers and table for both the channels information.

        Args:
            filtered_data (OrderedDict[str, Any]): An OrderedDict (sorted in order of model) mapping:
                module_fqns -> feature_names -> values
            channel_features (List[str]): A list of the channel level features
            num_channels (int): Number of channels in the channel data

        Returns a tuple with:
            A list of the headers of the channel table
            A list of lists containing the table information row by row
            The 0th index row will contain the headers of the columns
            The rest of the rows will contain data
        """
        # now we compose the table for the channel information table
        channel_table: List[List[Any]] = []
        channel_headers: List[str] = []

        # counter to keep track of number of entries in
        channel_table_entry_counter: int = 0

        if len(channel_features) > 0:
            # now we add all channel data
            for index, module_fqn in enumerate(filtered_data):
                # we iterate over all channels
                for channel in range(num_channels):
                    # we make a new row for the channel
                    new_channel_row = [channel_table_entry_counter, module_fqn, channel]
                    for feature in channel_features:
                        if feature in filtered_data[module_fqn]:
                            # add value if applicable to module
                            feature_val = filtered_data[module_fqn][feature][channel]
                        else:
                            # add that it is not applicable
                            feature_val = "Not Applicable"

                        # if it's a tensor we want to extract val
                        if type(feature_val) is torch.Tensor:
                            feature_val = feature_val.item()

                        # add value to channel specific row
                        new_channel_row.append(feature_val)

                    # add to table and increment row index counter
                    channel_table.append(new_channel_row)
                    channel_table_entry_counter += 1

        # add row of headers of we actually have something, otherwise just empty
        if len(channel_table) != 0:
            channel_headers = ["idx", "layer_fqn", "channel"] + channel_features

        return (channel_headers, channel_table)

    def generate_filtered_tables(self, feature_filter: str = "", module_fqn_filter: str = "") -> Dict[str, Tuple[List, List]]:
        r"""
        Takes in optional filter values and generates two tables with desired information.

        The generated tables are presented in both a list-of-lists format

        The reason for the two tables are that they handle different things:
        1.) the first table handles all tensor level information
        2.) the second table handles and displays all channel based information

        The reasoning for this is that having all the info in one table can make it ambiguous which collected
            statistics are global, and which are actually per-channel, so it's better to split it up into two
            tables. This also makes the information much easier to digest given the plethora of statistics collected

        Tensor table columns:
            idx  layer_fqn  feature_1   feature_2   feature_3   .... feature_n
            ----  ---------  ---------   ---------   ---------        ---------

        Per-Channel table columns:
            idx  layer_fqn  channel  feature_1   feature_2   feature_3   .... feature_n
            ----  ---------  -------  ---------   ---------   ---------        ---------

        Args:
            feature_filter (str, optional): Filters the features presented to only those that
                contain this filter substring
                Default = "", results in all the features being printed
            module_fqn_filter (str, optional): Only includes modules that contains this string
                Default = "", results in all the modules in the reports to be visible in the table

        Returns a dictionary with two keys:
            (Dict[str, Tuple[List, List]]) A dict containing two keys:
            "tensor_level_info", "channel_level_info"
                Each key maps to a tuple with:
                    A list of the headers of each table
                    A list of lists containing the table information row by row
                    The 0th index row will contain the headers of the columns
                    The rest of the rows will contain data

        Example Use:
            >>> mod_report_visualizer.generate_filtered_tables(
                    feature_filter = "per_channel_min",
                    module_fqn_filter = "block1"
                ) # generates table with per_channel_min info for all modules in block 1 of the model
        """
        # first get the filtered data
        filtered_data: OrderedDict[str, Any] = self._get_filtered_data(feature_filter, module_fqn_filter)

        # now we split into tensor and per-channel data
        tensor_features: Set[str] = set()
        channel_features: Set[str] = set()

        # keep track of the number of channels we have
        num_channels: int = 0

        for module_fqn in filtered_data:
            for feature_name in filtered_data[module_fqn]:
                # get the data for that specific feature
                feature_data = filtered_data[module_fqn][feature_name]

                # check if not zero dim tensor
                is_tensor: bool = isinstance(feature_data, torch.Tensor)
                is_not_zero_dim: bool = is_tensor and len(feature_data.shape) != 0

                if is_not_zero_dim or isinstance(feature_data, list):
                    # works means per channel
                    channel_features.add(feature_name)
                    num_channels = len(feature_data)
                else:
                    # means is per-tensor
                    tensor_features.add(feature_name)

        # we make them lists for iteration purposes
        tensor_features_list: List[str] = sorted(list(tensor_features))
        channel_features_list: List[str] = sorted(list(channel_features))

        # get the tensor info
        tensor_headers, tensor_table = self._generate_tensor_table(filtered_data, tensor_features_list)

        # get the channel info
        channel_headers, channel_table = self._generate_channels_table(
            filtered_data, channel_features_list, num_channels
        )

        # let's now create the dictionary to return
        table_dict = {
            self.TABLE_TENSOR_KEY : (tensor_headers, tensor_table),
            self.TABLE_CHANNEL_KEY : (channel_headers, channel_table)
        }

        # return the two tables
        return table_dict

    def generate_table_visualization(self, feature_filter: str = "", module_fqn_filter: str = ""):
        r"""
        Takes in optional filter values and prints out formatted tables of the information.

        The reason for the two tables printed out instead of one large one are that they handle different things:
        1.) the first table handles all tensor level information
        2.) the second table handles and displays all channel based information

        The reasoning for this is that having all the info in one table can make it ambiguous which collected
            statistics are global, and which are actually per-channel, so it's better to split it up into two
            tables. This also makes the information much easier to digest given the plethora of statistics collected

        Tensor table columns:
         idx  layer_fqn  feature_1   feature_2   feature_3   .... feature_n
        ----  ---------  ---------   ---------   ---------        ---------

        Per-Channel table columns:

         idx  layer_fqn  channel  feature_1   feature_2   feature_3   .... feature_n
        ----  ---------  -------  ---------   ---------   ---------        ---------

        Args:
            feature_filter (str, optional): Filters the features presented to only those that
                contain this filter substring
                Default = "", results in all the features being printed
            module_fqn_filter (str, optional): Only includes modules that contains this string
                Default = "", results in all the modules in the reports to be visible in the table

        Example Use:
            >>> mod_report_visualizer.generate_table_visualization(
                    feature_filter = "per_channel_min",
                    module_fqn_filter = "block1"
                )
            # prints out neatly formatted table with per_channel_min info for
                all modules in block 1 of the model
        """
        # see if we got tabulate
        if not got_tabulate:
            print("Make sure to install tabulate and try again.")
            return None

        # get the table dict and the specific tables of interest
        table_dict = self.generate_filtered_tables(feature_filter, module_fqn_filter)
        tensor_headers, tensor_table = table_dict[self.TABLE_TENSOR_KEY]
        channel_headers, channel_table = table_dict[self.TABLE_CHANNEL_KEY]

        # get the table string and print it out
        # now we have populated the tables for each one
        # let's create the strings to be returned
        table_str = ""
        # the tables will have some headers columns that are non-feature
        # ex. table index, module name, channel index, etc.
        # we want to look at header columns for features, that come after those headers
        if len(tensor_headers) > self.NUM_NON_FEATURE_TENSOR_HEADERS:
            # if we have at least one tensor level feature to be addded we add tensor table
            table_str += "Tensor Level Information \n"
            table_str += tabulate(tensor_table, headers=tensor_headers)
        if len(channel_headers) > self.NUM_NON_FEATURE_CHANNEL_HEADERS:
            # if we have at least one channel level feature to be addded we add tensor table
            table_str += "\n\n Channel Level Information \n"
            table_str += tabulate(channel_table, headers=channel_headers)

        # if no features at all, let user know
        if table_str == "":
            table_str = "No data points to generate table with."

        print(table_str)

    def _get_plottable_data(self, feature_filter: str, module_fqn_filter: str) -> Tuple[List, List[List], bool]:
        r"""
        Takes in the feature filters and module filters and outputs the x and y data for plotting

        Args:
            feature_filter (str): Filters the features presented to only those that
                contain this filter substring
            module_fqn_filter (str): Only includes modules that contains this string

        Returns a tuple of three elements
            The first is a list containing relavent x-axis data
            The second is a list containing the corresponding y-axis data
            If the data is per channel
        """
        # get the table dict and the specific tables of interest
        table_dict = self.generate_filtered_tables(feature_filter, module_fqn_filter)
        tensor_headers, tensor_table = table_dict[self.TABLE_TENSOR_KEY]
        channel_headers, channel_table = table_dict[self.TABLE_CHANNEL_KEY]

        # make sure it is only 1 feature that is being plotted
        # get the number of features in each of these
        tensor_info_features_count = len(tensor_headers) - ModelReportVisualizer.NUM_NON_FEATURE_TENSOR_HEADERS
        channel_info_features_count = len(channel_headers) - ModelReportVisualizer.NUM_NON_FEATURE_CHANNEL_HEADERS

        # see if valid tensor or channel plot
        is_valid_per_tensor_plot: bool = tensor_info_features_count == 1
        is_valid_per_channel_plot: bool = channel_info_features_count == 1

        # offset should either be one of tensor or channel table or neither
        feature_column_offset = ModelReportVisualizer.NUM_NON_FEATURE_TENSOR_HEADERS
        table = tensor_table

        # if a per_channel plot, we have different offset and table
        if is_valid_per_channel_plot:
            feature_column_offset = ModelReportVisualizer.NUM_NON_FEATURE_CHANNEL_HEADERS
            table = channel_table

        x_data: List = []
        y_data: List[List] = []
        # the feature will either be a tensor feature or channel feature
        if is_valid_per_tensor_plot or is_valid_per_channel_plot:
            # extra setup for y_data if per channel
            if is_valid_per_channel_plot:
                # gather the x_data and multiple y_data
                # calculate the number of channels
                num_channels: int = max(row[self.CHANNEL_NUM_INDEX] for row in table) + 1
                for channel in range(num_channels):
                    y_data.append([])  # seperate data list per channel

            for table_row_num, row in enumerate(table):
                # get x_value to append
                x_val_to_append = table_row_num
                current_channel: int = -1  # set current channel to be used if per channel
                if is_valid_per_channel_plot:
                    current_channel = row[self.CHANNEL_NUM_INDEX]  # intially chose current channel
                    new_module_index: int = table_row_num // num_channels
                    x_val_to_append = new_module_index

                # the index of the feature will the 0 + num non feature columns
                tensor_feature_index = feature_column_offset
                row_value = row[tensor_feature_index]
                if not type(row_value) == str:
                    # only append if new index we are appending
                    if len(x_data) == 0 or x_data[-1] != x_val_to_append:
                        x_data.append(x_val_to_append)
                    # how we append y value depends on if per tensor or not
                    if is_valid_per_channel_plot:
                        y_data[current_channel].append(row_value)
                    else:
                        y_data.append(row_value)
        else:
            # more than one feature was chosen
            error_str = "Make sure to pick only a single feature with your filter to plot a graph."
            error_str += " We recommend calling get_all_unique_feature_names() to find unique feature names."
            error_str += " Pick one of those features to plot."
            raise ValueError(error_str)

        # return x, y values, and if data is per-channel
        return (x_data, y_data, is_valid_per_channel_plot)

    def generate_plot_visualization(self, feature_filter: str, module_fqn_filter: str = ""):
        r"""
        Takes in a feature and optional module_filter and plots of the desired data.

        Note:
            Only features in the report that have tensor value data are plottable by this class
            When the tensor information is plotted, it will plot:
                idx as the x val, feature value as the y_val
            When the channel information is plotted, it will plot:
                the first idx of each module as the x val, feature value as the y_val [for each channel]
                The reason for this is that we want to be able to compare values across the
                channels for same layer, and it will be hard if values are staggered by idx
                This means each module is represented by only 1 x value
        Args:
            feature_filter (str): Filters the features presented to only those that
                contain this filter substring
            module_fqn_filter (str, optional): Only includes modules that contains this string
                Default = "", results in all the modules in the reports to be visible in the table

        Example Use:
            >>> mod_report_visualizer.generate_plot_visualization(
                    feature_filter = "per_channel_min",
                    module_fqn_filter = "block1"
                )
            # outputs line plot of per_channel_min information for all modules in block1 of model
                each channel gets it's own line, and it's plotted across the in-order modules
                on the x-axis
        """
        # checks if we have matplotlib and let's user know to install it if don't
        if not got_matplotlib:
            print("make sure to install matplotlib and try again.")
            return None

        # get the x and y data and if per channel
        x_data, y_data, data_per_channel = self._get_plottable_data(feature_filter, module_fqn_filter)

        # plot based on whether data is per channel or not
        ax = plt.subplot()
        ax.set_ylabel(feature_filter)
        ax.set_title(feature_filter + " Plot")
        plt.xticks(x_data)  # only show ticks for actual points

        if data_per_channel:
            ax.set_xlabel("First idx of module")
            # set the legend as well
            # plot a single line that is average of the channel values
            num_modules = len(y_data[0])  # all y_data have same length, so get num modules
            num_channels = len(y_data)  # we want num channels to be able to calculate average later

            avg_vals = [sum(y_data[:][index]) / num_channels for index in range(num_modules)]

            # plot the three things we measured
            ax.plot(x_data, avg_vals, label="Average Value Across {} Channels".format(num_channels))
            ax.legend(loc='upper right')
        else:
            ax.set_xlabel("idx")
            ax.plot(x_data, y_data)

        # actually show the plot
        plt.show()

    def generate_histogram_visualization(self, feature_filter: str, module_fqn_filter: str = "", num_bins: int = 10):
        r"""
        Takes in a feature and optional module_filter and plots the histogram of desired data.

        Note:
            Only features in the report that have tensor value data can be viewed as a histogram
            If you want to plot a histogram from all the channel values of a specific feature for
                a specific model, make sure to specify both the model and the feature properly
                in the filters and you should be able to see a distribution of the channel data

        Args:
            feature_filter (str, optional): Filters the features presented to only those that
                contain this filter substring
                Default = "", results in all the features being printed
            module_fqn_filter (str, optional): Only includes modules that contains this string
                Default = "", results in all the modules in the reports to be visible in the table
            num_bins (int, optional): The number of bins to create the histogram with
                Default = 10, the values will be split into 10 equal sized bins

        Example Use:
            >>> mod_report_visualizer.generategenerate_histogram_visualization_plot_visualization(
                    feature_filter = "per_channel_min",
                    module_fqn_filter = "block1"
                )
            # outputs histogram of per_channel_min information for all modules in block1 of model
                information is gathered across all channels for all modules in block 1 for the
                per_channel_min and is displayed in a histogram of equally sized bins
        """
        # checks if we have matplotlib and let's user know to install it if don't
        if not got_matplotlib:
            print("make sure to install matplotlib and try again.")
            return None

        # get the x and y data and if per channel
        x_data, y_data, data_per_channel = self._get_plottable_data(feature_filter, module_fqn_filter)

        # for histogram, we just care about plotting the y data
        # plot based on whether data is per channel or not
        ax = plt.subplot()
        ax.set_xlabel(feature_filter)
        ax.set_ylabel("Frequency")
        ax.set_title(feature_filter + " Histogram")

        if data_per_channel:
            # set the legend as well
            # combine all the data
            all_data = []
            for index, channel_info in enumerate(y_data):
                all_data.extend(channel_info)

            val, bins, _ = plt.hist(
                all_data,
                bins=num_bins,
                stacked=True,
                rwidth=0.8,
            )
            plt.xticks(bins)
        else:
            val, bins, _ = plt.hist(
                y_data,
                bins=num_bins,
                stacked=False,
                rwidth=0.8,
            )
            plt.xticks(bins)

        plt.show()
