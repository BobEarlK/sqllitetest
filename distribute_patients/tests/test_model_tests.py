import math
from django.db.models import Avg, Count
from django.test import TestCase
from django.utils import timezone

from ..helper_fxns import helper_fxn_create_distribution_with_4_sample_line_items, \
    helper_fxn_create_motley_list_of_patients_assign_to_distribution, \
    helper_fxn_create_list_of_bounceback_patients_assign_to_distribution, \
    helper_fxn_create_distribution_with_up_to_4_sample_line_items
from ..models import Distribution, Patient, PatientAssignmentLineItem, Provider, StartingCensus, AssignedCensus, \
    AllocatedCounts, OptimalCensus


class PatientAssignmentLineItemTests(TestCase):
    def test_can_create_patient_assignment_line_item(self):
        provider = Provider.objects.create()
        distribution = Distribution.objects.create()
        starting_total, starting_CCU, starting_COVID = 10, 3, 4
        assignment_line_item = PatientAssignmentLineItem.objects.create_line_item(distribution=distribution,
                                                                                  provider=provider,
                                                                                  starting_total=starting_total,
                                                                                  starting_CCU=starting_CCU,
                                                                                  starting_COVID=starting_COVID,
                                                                                  position_in_batting_order=1)
        self.assertIsInstance(assignment_line_item, PatientAssignmentLineItem)

    def test_new_patient_assignment_line_item_starts_with_no_assigned_patients(self):
        provider = Provider.objects.create()
        distribution = Distribution.objects.create()
        starting_total, starting_CCU, starting_COVID = 10, 3, 4
        assignment_line_item = PatientAssignmentLineItem.objects.create_line_item(distribution=distribution,
                                                                                  provider=provider,
                                                                                  starting_total=starting_total,
                                                                                  starting_CCU=starting_CCU,
                                                                                  starting_COVID=starting_COVID,
                                                                                  position_in_batting_order=1)
        self.assertEqual(assignment_line_item.assigned_patients.all().count(), 0)

    def test_new_patient_assignment_line_item_starts_with_optimal_census_set_to_starting_census(self):
        provider = Provider.objects.create()
        distribution = Distribution.objects.create()
        starting_total, starting_CCU, starting_COVID = 10, 3, 4
        assignment_line_item = PatientAssignmentLineItem.objects.create_line_item(distribution=distribution,
                                                                                  provider=provider,
                                                                                  starting_total=starting_total,
                                                                                  starting_CCU=starting_CCU,
                                                                                  starting_COVID=starting_COVID,
                                                                                  position_in_batting_order=1)
        self.assertEqual(assignment_line_item.optimal_census.total, 10)
        self.assertEqual(assignment_line_item.optimal_census.CCU, 3)
        self.assertEqual(assignment_line_item.optimal_census.COVID, 4)

    def test_new_patient_assignment_line_item_starts_with_assigned_census_equal_to_starting_census(self):
        provider = Provider.objects.create()
        distribution = Distribution.objects.create()
        starting_total, starting_CCU, starting_COVID = 10, 3, 4
        assignment_line_item = PatientAssignmentLineItem.objects.create_line_item(distribution=distribution,
                                                                                  provider=provider,
                                                                                  starting_total=starting_total,
                                                                                  starting_CCU=starting_CCU,
                                                                                  starting_COVID=starting_COVID,
                                                                                  position_in_batting_order=1)
        self.assertEqual(assignment_line_item.assigned_census.total, assignment_line_item.starting_census.total)
        self.assertEqual(assignment_line_item.assigned_census.CCU, assignment_line_item.starting_census.CCU)
        self.assertEqual(assignment_line_item.assigned_census.COVID, assignment_line_item.starting_census.COVID)

    def test_can_retrieve_distribution_patient_assignment_line_items_in_batting_order(self):
        helper_fxn_create_distribution_with_4_sample_line_items()
        self.assertEqual(Distribution.objects.last().line_items.count(), 4)
        self.assertEqual([line_item.starting_census.total for line_item in
                          Distribution.objects.last().get_ordered_line_items()],
                         [11, 13, 10, 11])
        self.assertEqual([line_item.starting_census.COVID for line_item in
                          Distribution.objects.last().get_ordered_line_items()],
                         [3, 1, 0, 2])
        self.assertEqual([line_item.starting_census.CCU for line_item in
                          Distribution.objects.last().get_ordered_line_items()],
                         [3, 2, 2, 1])


class OptimalAssignPatientsToLineItems(TestCase):
    def setUp(self):
        helper_fxn_create_distribution_with_4_sample_line_items()
        self.distribution = Distribution.objects.last()

    def test_can_print_starting_censuses(self):
        self.distribution.print_starting_censuses()

    def test_assigned_census_equals_starting_census_after_line_items_created(self):
        for line_item in self.distribution.get_ordered_line_items():
            self.assertEqual(line_item.assigned_census.total, line_item.starting_census.total)
            self.assertEqual(line_item.assigned_census.CCU, line_item.starting_census.CCU)
            self.assertEqual(line_item.assigned_census.COVID, line_item.starting_census.COVID)

    def test_can_print_assigned_censuses(self):
        self.distribution.print_assigned_censuses()

    def test_helper_fxn_create_distribution_patients_works(self):
        helper_fxn_create_motley_list_of_patients_assign_to_distribution(patient_count=20,
                                                                         distribution=self.distribution)
        self.assertEqual(self.distribution.patient_set.count(), 20)
        for patient in self.distribution.patient_set.all():
            self.assertEqual(patient.distribution, self.distribution)

    def test_calculate_optimal_census_correctly_allocates_1_pt_to_listed_attending(self):
        Patient.objects.create(distribution=self.distribution, COVID=True, CCU=False, number_designation=1,
                               bounce_to=Provider.objects.get_or_create(abbreviation='provC')[0])
        self.distribution.calculate_optimal_census()
        expected_totals = [11, 14, 10, 11]
        self.assertEqual([line_item.optimal_census.total for line_item in
                          self.distribution.get_ordered_line_items()], expected_totals)

    def test_calculate_optimal_census_allocates_bounceback_pts_to_listed_attending(self):
        helper_fxn_create_list_of_bounceback_patients_assign_to_distribution(patient_count=9,
                                                                             distribution=self.distribution)
        self.distribution.calculate_optimal_census()
        expected_totals = [15, 18, 10, 11]
        self.assertEqual([line_item.optimal_census.total for line_item in
                          self.distribution.get_ordered_line_items()], expected_totals)

    def test_calculate_optimal_census_allocates_mixed_pts_to_listed_attending(self):
        helper_fxn_create_list_of_bounceback_patients_assign_to_distribution(patient_count=9,
                                                                             distribution=self.distribution)
        helper_fxn_create_motley_list_of_patients_assign_to_distribution(patient_count=4,
                                                                         distribution=self.distribution)
        self.distribution.calculate_optimal_census()
        expected_totals = [15, 18, 12, 13]
        self.assertEqual([line_item.optimal_census.total for line_item in
                          self.distribution.get_ordered_line_items()], expected_totals)

    def test_can_set_optimal_census_total_given_starting_censuses_and_patient_list_after_allocate_bb_pts(self):
        helper_fxn_create_motley_list_of_patients_assign_to_distribution(patient_count=30,
                                                                         distribution=self.distribution)
        self.distribution.calculate_optimal_census()
        expected_totals = [18, 19, 19, 19]
        self.assertEqual([line_item.optimal_census.total for line_item in self.distribution.get_ordered_line_items()],
                         expected_totals)

    def test_can_set_optimal_census_CCU_given_starting_censuses_and_patient_list(self):
        helper_fxn_create_motley_list_of_patients_assign_to_distribution(patient_count=30,
                                                                         distribution=self.distribution)
        self.distribution.calculate_optimal_census()
        expected_totals = [18, 19, 19, 19]
        self.assertEqual([line_item.optimal_census.total for line_item in self.distribution.get_ordered_line_items()],
                         expected_totals)
        expected_CCU = [4.32, 4.56, 4.56, 4.56]
        self.assertEqual([round(line_item.optimal_census.CCU, 2) for line_item in
                          self.distribution.get_ordered_line_items()], expected_CCU)

    def test_can_set_optimal_census_COVID_given_starting_censuses_and_patient_list(self):
        helper_fxn_create_motley_list_of_patients_assign_to_distribution(patient_count=30,
                                                                         distribution=self.distribution)
        self.distribution.calculate_optimal_census()
        expected_totals = [18, 19, 19, 19]
        self.assertEqual([line_item.optimal_census.total for line_item in self.distribution.get_ordered_line_items()],
                         expected_totals)
        expected_COVID = [5.04, 5.32, 5.32, 5.32]
        self.assertEqual([round(line_item.optimal_census.COVID, 2) for line_item in
                          self.distribution.get_ordered_line_items()], expected_COVID)

    def test_can_return_distance_from_optimal_for_any_line_item(self):
        line_item = self.distribution.get_ordered_line_items()[0]
        # should be starting at 11 (3) (3), will dummy up some optimal line items to confirm the distance
        line_item.optimal_census = OptimalCensus(total=13, CCU=4, COVID=4)
        self.assertEqual(round(line_item.get_distance_from_assigned_census_to_optimal(), 2), 1.41)
        line_item.optimal_census = OptimalCensus(total=14, CCU=5, COVID=4)
        self.assertEqual(round(line_item.get_distance_from_assigned_census_to_optimal(), 2), 2.24)
        line_item.optimal_census = OptimalCensus(total=18, CCU=7, COVID=6)
        self.assertEqual(round(line_item.get_distance_from_assigned_census_to_optimal(), 2), 5)

    def test_can_return_change_in_distance_from_optimal_by_adding_given_pt(self):
        line_item = self.distribution.get_ordered_line_items()[0]
        # should be starting at 11 (3) (3), will dummy up some optimal line items to confirm the distance
        line_item.optimal_census = OptimalCensus(total=18, CCU=7, COVID=6)
        self.assertEqual(round(line_item.get_distance_from_assigned_census_to_optimal(), 2), 5)
        patient = Patient.objects.create(CCU=True, COVID=True, number_designation=1, distribution=self.distribution)
        self.assertEqual(round(line_item.get_distance_moved_closer_to_optimal_after_adding_patient(patient=patient), 2),
                         round(5 - math.sqrt(13), 2))
        patient = Patient.objects.create(CCU=True, COVID=False, number_designation=2, distribution=self.distribution)
        self.assertEqual(round(line_item.get_distance_moved_closer_to_optimal_after_adding_patient(patient=patient), 2),
                         round(5 - math.sqrt(18), 2))
        patient = Patient.objects.create(CCU=False, COVID=True, number_designation=3, distribution=self.distribution)
        self.assertEqual(round(line_item.get_distance_moved_closer_to_optimal_after_adding_patient(patient=patient), 2),
                         round(5 - math.sqrt(20), 2))
        patient = Patient.objects.create(CCU=False, COVID=False, number_designation=4, distribution=self.distribution)
        self.assertEqual(round(line_item.get_distance_moved_closer_to_optimal_after_adding_patient(patient=patient), 2),
                         0)

    def test_can_return_line_item_moved_furthest_distance_toward_optimal_by_assignment_of_given_patient(self):
        # will dummy up line items so as to make it clear which one benefits most from a given patient
        # first we'll narrow to two line items, and add them back later for comparison
        distribution = Distribution.objects.create()
        #  line item 1 will start with too many COVIDs and CCUs, so adding should take it further; will be last
        line_item1 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=1, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=19, CCU=6, COVID=6),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provA')[0])
        # line item 2 will start w optimal number of COVID, too many CCUs, adding will take it further, next to last
        line_item2 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=2, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=19, CCU=6, COVID=5),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provB')[0])
        patient = Patient.objects.create(CCU=True, COVID=True, number_designation=1, distribution=distribution)
        self.assertEqual(line_item2, distribution.get_line_item_moved_furthest_toward_optimal_by_adding_patient(
            patient=patient))
        # line item 3 will mostly need COVIDs than CCU's, so will come in 2nd
        line_item3 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=3, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=19, CCU=4, COVID=2),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provB')[0])
        self.assertEqual(line_item3, distribution.get_line_item_moved_furthest_toward_optimal_by_adding_patient(
            patient=patient))
        # line item 4 needs same number of COVIDs and CCUs, and will come in first
        line_item4 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=4, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=19, CCU=2, COVID=2),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provB')[0])
        self.assertEqual(line_item4, distribution.get_line_item_moved_furthest_toward_optimal_by_adding_patient(
            patient=patient))

    def test_only_return_furthest_distance_line_item_if_it_has_space_for_patient(self):
        # same as prior example, but only the least desirable line item has room for any total patients
        distribution = Distribution.objects.create()
        #  line item 1 here, as previous, is lowest priority, but is the only one with space
        line_item1 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=1, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=19, CCU=6, COVID=6),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provA')[0])
        # line item 2 would get a more favorable score as in prior test, but is full (assigned_total = optimal total)
        line_item2 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=2, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=20, CCU=6, COVID=5),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provB')[0])
        patient = Patient.objects.create(CCU=True, COVID=True, number_designation=1, distribution=distribution)
        self.assertEqual(line_item1, distribution.get_line_item_moved_furthest_toward_optimal_by_adding_patient(
            patient=patient))
        # line item 3 will mostly need COVIDs than CCU's, so will come in 2nd
        line_item3 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=3, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=20, CCU=4, COVID=2),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provB')[0])
        self.assertEqual(line_item1, distribution.get_line_item_moved_furthest_toward_optimal_by_adding_patient(
            patient=patient))
        # line item 4 needs same number of COVIDs and CCUs, and will come in first
        line_item4 = PatientAssignmentLineItem.objects.create(
            position_in_batting_order=4, distribution=distribution,
            optimal_census=OptimalCensus.objects.create(total=20, CCU=5, COVID=5),
            assigned_census=AssignedCensus.objects.create(total=20, CCU=2, COVID=2),
            starting_census=StartingCensus.objects.create(total=3, CCU=1, COVID=6),
            provider=Provider.objects.get_or_create(abbreviation='provB')[0])
        self.assertEqual(line_item1, distribution.get_line_item_moved_furthest_toward_optimal_by_adding_patient(
            patient=patient))



    def test_can_assign_pt_to_line_item(self):
        patient = Patient.objects.create(number_designation=1, distribution=self.distribution)
        line_item = self.distribution.get_ordered_line_items().first()
        line_item.assign_patient(patient)
        self.assertEqual(patient.patient_assignment_line_item, line_item)

    def test_assigning_pt_to_line_item_changes_assigned_patient_numbers(self):
        patient = Patient.objects.create(number_designation=1, distribution=self.distribution)
        line_item = self.distribution.get_ordered_line_items().first()
        line_item.assign_patient(patient)
        starting_total = [11,13,10,11]
        starting_CCU = [3,2,2,1]
        starting_COVID=[3,1,0,2]
        assigned_total = [12,13,10,11]
        assigned_CCU =[3,2,2,1]
        assigned_COVID=[3,1,0,2]
        self.assertEqual([line_item.starting_census.total for line_item in self.distribution.get_ordered_line_items()],
                         starting_total)
        self.assertEqual([line_item.starting_census.CCU for line_item in self.distribution.get_ordered_line_items()],
                         starting_CCU)
        self.assertEqual([line_item.starting_census.COVID for line_item in self.distribution.get_ordered_line_items()],
                         starting_COVID)
        self.assertEqual([line_item.assigned_census.total for line_item in self.distribution.get_ordered_line_items()],
                         assigned_total)
        self.assertEqual([line_item.assigned_census.CCU for line_item in self.distribution.get_ordered_line_items()],
                         assigned_CCU)
        self.assertEqual([line_item.assigned_census.COVID for line_item in self.distribution.get_ordered_line_items()],
                         assigned_COVID)
        patient = Patient.objects.create(number_designation=1, distribution=self.distribution, CCU=True, COVID=True)
        line_item = self.distribution.get_ordered_line_items().all()[3]
        line_item.assign_patient(patient)
        starting_total = [11,13,10,11]
        starting_CCU = [3,2,2,1]
        starting_COVID=[3,1,0,2]
        assigned_total = [12,13,10,12]
        assigned_CCU =[3,2,2,2]
        assigned_COVID=[3,1,0,3]
        self.assertEqual([line_item.starting_census.total for line_item in self.distribution.get_ordered_line_items()],
                         starting_total)
        self.assertEqual([line_item.starting_census.CCU for line_item in self.distribution.get_ordered_line_items()],
                         starting_CCU)
        self.assertEqual([line_item.starting_census.COVID for line_item in self.distribution.get_ordered_line_items()],
                         starting_COVID)
        self.assertEqual([line_item.assigned_census.total for line_item in self.distribution.get_ordered_line_items()],
                         assigned_total)
        self.assertEqual([line_item.assigned_census.CCU for line_item in self.distribution.get_ordered_line_items()],
                         assigned_CCU)
        self.assertEqual([line_item.assigned_census.COVID for line_item in self.distribution.get_ordered_line_items()],
                         assigned_COVID)
        self.distribution.print_starting_censuses()
        self.distribution.print_assigned_censuses()


class AssignAllPatientsToLineItems(TestCase):
    def test_can_assign_all_patients_to_line_items(self):
        for patient_count in range(1,12):
            helper_fxn_create_distribution_with_4_sample_line_items()
            distribution = Distribution.objects.last()
            Patient.objects.all().delete()
            helper_fxn_create_motley_list_of_patients_assign_to_distribution(patient_count=patient_count,
                                                                             distribution=distribution)
            distribution.assign_all_patients()
            distribution.print_assigned_censuses()
            if patient_count == 1:
                # 1st patient is bounceback to li 1, third in ordered line items, and is COVID pos, CCU pos
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [11, 13, 11, 11]
                assigned_CCU = [3, 2, 3, 1]
                assigned_COVID = [3, 1, 1, 2]
            if patient_count == 2:
                # 2nd patient is not a bounce and is COVID neg, CCU neg
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [11, 13, 11, 12]
                assigned_CCU = [3, 2, 3, 1]
                assigned_COVID = [3, 1, 1, 2]
            if patient_count == 3:
                # 3rd patient is not a bounce and is COVID pos, CCU neg
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [11, 13, 12, 12]
                assigned_CCU = [3, 2, 3, 1]
                assigned_COVID = [3, 1, 2, 2]
            if patient_count == 4:
                # 4th patient is not a bounce and is COVID neg, CCU pos
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [12, 13, 12, 12]
                assigned_CCU = [3, 2, 3, 2]
                assigned_COVID = [3, 1, 2, 2]
            if patient_count == 5:
                # 5th patient is not a bounce and is COVID pos, CCU neg
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [12, 13, 12, 13]
                assigned_CCU = [3, 2, 3, 2]
                assigned_COVID = [3, 1, 2, 3]
            if patient_count == 6:
                # 6th patient is bounceback to li 1, 1st in ordered line items, and is COVID neg, CCU neg
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [12, 13, 13, 13]
                assigned_CCU = [3, 2, 3, 2]
                assigned_COVID = [3, 1, 2, 3]
            if patient_count == 7:
                # 7th patient is not a bounce and is COVID pos, CCU pos
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [13, 13, 13, 13]
                assigned_CCU = [3, 2, 3, 3]
                assigned_COVID = [3, 1, 3, 3]
            if patient_count == 8:
                # 8th patient is not a bounce and is COVID neg, CCU neg
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [13, 13, 13, 14]
                assigned_CCU = [3, 2, 3, 3]
                assigned_COVID = [3, 1, 3, 3]
            if patient_count == 9:
                # 9th patient is not a bounce and is COVID pos, CCU neg
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [13, 13, 14, 14]
                assigned_CCU = [3, 2, 3, 3]
                assigned_COVID = [4, 1, 3, 3]
            if patient_count == 10:
                # 10th patient is not a bounce and is COVID neg, CCU pos
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [13, 14, 14, 14]
                assigned_CCU = [3, 3, 3, 3]
                assigned_COVID = [3, 2, 3, 3]
            if patient_count == 11:
                # 11th patient is a bounce to li 3 in position 2, and is  and is COVID pos, CCU neg
                starting_total = [11, 13, 10, 11]
                starting_CCU = [3, 2, 2, 1]
                starting_COVID = [3, 1, 0, 2]
                assigned_total = [14, 14, 14, 14]
                assigned_CCU = [3, 2, 4, 3]
                assigned_COVID = [4, 2, 3, 3]
            self.assertEqual(
                [line_item.starting_census.total for line_item in distribution.get_ordered_line_items()],
                starting_total)
            self.assertEqual(
                [line_item.starting_census.CCU for line_item in distribution.get_ordered_line_items()],
                starting_CCU)
            self.assertEqual(
                [line_item.starting_census.COVID for line_item in distribution.get_ordered_line_items()],
                starting_COVID)
            self.assertEqual(
                [line_item.assigned_census.total for line_item in distribution.get_ordered_line_items()],
                assigned_total)
            self.assertEqual(
                [line_item.assigned_census.CCU for line_item in distribution.get_ordered_line_items()],
                assigned_CCU)
            self.assertEqual(
                [line_item.assigned_census.COVID for line_item in distribution.get_ordered_line_items()],
                assigned_COVID)


class OrderNonBouncebackPatientTestsTests(TestCase):
    def setUp(self):
        provider = Provider.objects.create()
        self.distribution = Distribution.objects.create()
        starting_total, starting_CCU, starting_COVID = 10, 3, 4
        self.assignment_line_item = PatientAssignmentLineItem.objects.create_line_item(distribution=self.distribution,
                                                                                       provider=provider,
                                                                                       starting_total=starting_total,
                                                                                       starting_CCU=starting_CCU,
                                                                                       starting_COVID=starting_COVID,
                                                                                       position_in_batting_order=1)


    def test_get_ordered_patients_prioritizes_dual_pos_then_ccu_pos_then_cov_pos(self):
        """
        postulating that COVID_positive_CCU_positive patients can skew the distribution, those patients should
        immediately follow bouncebacks in assignment:  bouncebacks, CCU/COVID, CCU, COVID, both negative
        """
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=1, distribution=self.distribution, CCU=True, COVID=True))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=2, distribution=self.distribution, CCU=True, COVID=False))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=3, distribution=self.distribution, CCU=False, COVID=True))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=4, distribution=self.distribution, CCU=False,
                                           COVID=False))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=5, distribution=self.distribution, CCU=True, COVID=True))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=6, distribution=self.distribution, CCU=True, COVID=False))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=7, distribution=self.distribution, CCU=False, COVID=True))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=8, distribution=self.distribution, CCU=False,
                                           COVID=False, bounce_to=Provider.objects.first()))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=9, distribution=self.distribution, CCU=True, COVID=True,
                                           bounce_to=Provider.objects.first()))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=10, distribution=self.distribution, CCU=True,
                                           COVID=False))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=11, distribution=self.distribution, CCU=False,
                                           COVID=True, bounce_to=Provider.objects.first()))
        self.assignment_line_item.assign_patient(
            patient=Patient.objects.create(number_designation=12, distribution=self.distribution, CCU=False,
                                           COVID=False, bounce_to=Provider.objects.first()))
        ordered_patients = self.distribution.get_ordered_non_bounceback_patients_for_assignment()
        self.assertEqual([patient.number_designation for patient in ordered_patients],
                         [1, 5, 2, 6, 10, 3, 7, 4])


class DistributionTests(TestCase):
    def test_add_duplicated_line_items_method_duplicates_line_items_of_most_recent_distribution(self):
        helper_fxn_create_distribution_with_4_sample_line_items()
        new_distribution = Distribution.objects.create()
        new_distribution.add_duplicated_line_items_from_prior_distribution()
        self.assertEqual(new_distribution.get_ordered_line_items().count(), 4)
        self.assertEqual([line_item.starting_census.total for line_item in new_distribution.get_ordered_line_items()],
                         [11, 13, 10, 11])
        self.assertEqual(Distribution.objects.count(), 2)


class DistributionPatientMethodsTests(TestCase):
    def setUp(self):
        self.distribution = Distribution.objects.create()
        for i in range(30):
            if i in range(10, 22):
                covid = True
            else:
                covid = False
            if i in range(15, 25):
                ccu = True
            else:
                ccu = False
            Patient.objects.create(distribution=self.distribution, number_designation=i + 1, CCU=ccu, COVID=covid)

    def test_given_distribution_with_assigned_patients_can_get_allocation_numbers(self):
        self.assertEqual(self.distribution.patient_set.all().count(), 30)
        self.assertEqual(self.distribution.patient_set.filter(CCU=True).count(), 10)
        self.assertEqual(self.distribution.patient_set.filter(COVID=True).count(), 12)


