class MigrationOptimizer:
    """
    Power the optimization process, where you provide a list of Operations
    and you are returned a list of equal or shorter length - operations
    are merged into one if possible.

    For example, a CreateModel and an AddField can be optimized into a
    new CreateModel, and CreateModel and DeleteModel can be optimized into
    nothing.
    """

    def optimize(self, operations, app_label):
        """
        Main optimization entry point. Pass in a list of Operation instances,
        get out a new list of Operation instances.

        Unfortunately, due to the scope of the optimization (two combinable
        operations might be separated by several hundred others), this can't be
        done as a peephole optimization with checks/output implemented on
        the Operations themselves; instead, the optimizer looks at each
        individual operation and scans forwards in the list to see if there
        are any matches, stopping at boundaries - operations which can't
        be optimized over (RunSQL, operations on the same field/model, etc.)

        The inner loop is run until the starting list is the same as the result
        list, and then the result is returned. This means that operation
        optimization must be stable and always return an equal or shorter list.
        """
        # Internal tracking variable for test assertions about # of loops
        if app_label is None:
            raise TypeError("app_label must be a str.")
        self._iterations = 0
        # MIGOPT-008 architecture contract: MigrationOptimizer owns repeated
        # application of operation-level reductions. A replacement AddField is
        # therefore returned to the same optimization region, where its reducer
        # may consume each later applicable same-target AlterField in sequence.
        while True:
            result = self.optimize_inner(operations, app_label)
            self._iterations += 1
            if result == operations:
                return result
            operations = result

    def optimize_inner(self, operations, app_label):
        """Inner optimization loop."""
        new_operations = []
        for i, operation in enumerate(operations):
            right = True  # Should we reduce on the right or on the left.
            # MIGOPT-007 architecture contract: optimize_inner() owns traversal
            # within one supplied optimization region. Operation.reduce() owns
            # pair eligibility and traversal permission; a denied permission is
            # a hard seam that this layer must neither reorder nor cross.
            # MIGOPT-007 -- intervening-operation reduction boundary:
            # INPUT: a candidate operation, each later operation, and the
            # ordered operations between that pair.
            # FOR each later operation, request a pair reduction without
            # removing or reordering any intervening operation in advance.
            # IF the pair is reducible on the current traversal side, accept it
            # only when every intervening operation explicitly permits the
            # required traversal; then retain the intervening operations in
            # their valid relative order around the replacement.
            # ELSE mark that traversal direction as blocked and continue only
            # along a direction still permitted by the encountered operations.
            # IF any intervening operation prevents the required traversal,
            # reject reduction across it, append the original operation, and
            # leave both same-field AlterField operations in the result.
            # OUTPUT: a reduction confined to one uninterrupted optimizable
            # region, or the unchanged operations at the blocking boundary.
            # Compare it to each operation after it
            for j, other in enumerate(operations[i + 1 :]):
                result = operation.reduce(other, app_label)
                if isinstance(result, list):
                    in_between = operations[i + 1 : i + j + 1]
                    if right:
                        new_operations.extend(in_between)
                        new_operations.extend(result)
                    elif all(op.reduce(other, app_label) is True for op in in_between):
                        # Perform a left reduction if all of the in-between
                        # operations can optimize through other.
                        new_operations.extend(result)
                        new_operations.extend(in_between)
                    else:
                        # Otherwise keep trying.
                        new_operations.append(operation)
                        break
                    new_operations.extend(operations[i + j + 2 :])
                    return new_operations
                elif not result:
                    # Can't perform a right reduction.
                    right = False
            else:
                new_operations.append(operation)
        return new_operations
