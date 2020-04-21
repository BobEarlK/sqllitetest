import math
from django.db import models
from django.db.models import Avg, Sum, Count
from django.shortcuts import reverse
from django.utils import timezone


class DistributionManager(models.Manager):
    def create(self, *args, **kwargs):  # creates new line_items from prior distribution, if any
        try:
            prior_distribution = Distribution.objects.last()
        except Distribution.DoesNotExist:
            prior_distribution = None
        new_distribution = super().create(**kwargs)
        if prior_distribution:
            for line_item in prior_distribution.get_ordered_line_items():
                new_line_item = PatientAssignmentLineItem.objects.create_line_item(
                    provider=line_item.provider, starting_total=line_item.starting_census.total,
                    starting_CCU=line_item.starting_census.total, starting_COVID=line_item.starting_census.COVID,
                    position_in_batting_order=line_item.position_in_batting_order, distribution=new_distribution)
        return new_distribution


class Distribution(models.Model):
    count_to_distribute = models.SmallIntegerField(null=True, blank=True)

    def get_ordered_line_items(self):
        return self.line_items.order_by('position_in_batting_order')

    def add_duplicated_line_items_from_prior_distribution(self):
        if prior_distribution := Distribution.objects.exclude(id=self.id).last():
            for line_item in prior_distribution.get_ordered_line_items():
                PatientAssignmentLineItem.objects.create_line_item(
                    provider=line_item.provider, starting_total=line_item.starting_census.total,
                    starting_CCU=line_item.starting_census.CCU, starting_COVID=line_item.starting_census.COVID,
                    position_in_batting_order=line_item.position_in_batting_order, distribution=self)

    def get_bounceback_patients(self):
        return self.patient_set.filter(bounce_to__isnull=False)

    def get_ordered_non_bounceback_patients_for_assignment(self):
        return self.patient_set.filter(bounce_to__isnull=True).order_by('-CCU', '-COVID', 'number_designation')

    def print_starting_censuses(self):
        for line_item in self.get_ordered_line_items():
            print(f'LI{line_item.id}: {line_item.starting_census.total} ' + \
                  f'({line_item.starting_census.CCU}) [{line_item.starting_census.COVID}]')

    def print_optimal_censuses(self):
        for line_item in self.get_ordered_line_items():
            print(f'LI{line_item.id}: {line_item.optimal_census.total} ' + \
                  f'({line_item.optimal_census.CCU}) [{line_item.optimal_census.COVID}]')

    def print_assigned_censuses(self):
        for line_item in self.get_ordered_line_items():
            print(f'LI{line_item.id}: {line_item.assigned_census.total} ' + \
                  f'({line_item.assigned_census.CCU}) [{line_item.assigned_census.COVID}]')

    def calculate_optimal_census(self):
        self.allocate_bounceback_patients()
        self.set_optimal_census_total()
        self.set_optimal_census_CCU_and_COVID()

    def set_optimal_census_total(self):
        non_bounceback_patient_count = self.patient_set.filter(bounce_to__isnull=True).count()
        ordered_line_items = self.get_ordered_line_items()
        for i in range(non_bounceback_patient_count):
            line_item_with_last_lowest_total = None
            for index, line_item in enumerate(ordered_line_items):
                if line_item_with_last_lowest_total == None:
                    line_item_with_last_lowest_total = line_item
                elif line_item.optimal_census.total <= line_item_with_last_lowest_total.optimal_census.total:
                    line_item_with_last_lowest_total = line_item
            line_item_with_last_lowest_total.optimal_census.total += 1
            line_item_with_last_lowest_total.optimal_census.save()

    def set_optimal_census_CCU_and_COVID(self):
        starting_CCU_aggregate_census = self.get_ordered_line_items().aggregate(sum=Sum('starting_census__CCU'))
        aggregate_CCU_census_of_patients_to_distribute = self.patient_set.filter(CCU=True).count()
        starting_COVID_aggregate_census = self.get_ordered_line_items().aggregate(sum=Sum('starting_census__COVID'))
        aggregate_COVID_census_of_patients_to_distribute = self.patient_set.filter(COVID=True).count()
        line_item_count = self.get_ordered_line_items().count()
        optimal_total_census_average = self.get_ordered_line_items().aggregate(avg=Avg('optimal_census__total'))
        optimal_CCU_census = \
            (starting_CCU_aggregate_census['sum'] + \
             aggregate_CCU_census_of_patients_to_distribute) / line_item_count
        optimal_COVID_census = \
            (starting_COVID_aggregate_census['sum'] + \
             aggregate_COVID_census_of_patients_to_distribute) / line_item_count
        for line_item in self.get_ordered_line_items():
            total_census_weighting_factor = line_item.optimal_census.total / optimal_total_census_average['avg']
            line_item.optimal_census.CCU = total_census_weighting_factor * optimal_CCU_census
            line_item.optimal_census.COVID = total_census_weighting_factor * optimal_COVID_census
            line_item.optimal_census.save()

    def allocate_bounceback_patients(self):
        bounceback_patients = self.get_bounceback_patients()
        for bounceback_patient in bounceback_patients:
            line_item = self.line_items.get(provider=bounceback_patient.bounce_to)
            line_item.optimal_census.total += 1
            if bounceback_patient.CCU:
                line_item.optimal_census.CCU += 1
            if bounceback_patient.COVID:
                line_item.optimal_census.COVID += 1
            line_item.optimal_census.save()

    def get_line_item_moved_furthest_toward_optimal_by_adding_patient(self, patient):
        line_item_moved_furthest_toward_optimal = None
        for line_item in self.get_ordered_line_items():
            if line_item.assigned_census.total < line_item.optimal_census.total:
                if not line_item_moved_furthest_toward_optimal:
                    line_item_moved_furthest_toward_optimal = line_item
                elif line_item.get_distance_moved_closer_to_optimal_after_adding_patient(patient=patient) > \
                        line_item_moved_furthest_toward_optimal.get_distance_moved_closer_to_optimal_after_adding_patient(
                            patient=patient):
                    line_item_moved_furthest_toward_optimal = line_item
        if not line_item_moved_furthest_toward_optimal:
            raise ValueError('There are no line items with space for another patient')
        return line_item_moved_furthest_toward_optimal


    def assign_bounceback_patients(self):
        bounceback_patients = self.get_bounceback_patients()
        for bounceback_patient in bounceback_patients:
            line_item = self.line_items.get(provider=bounceback_patient.bounce_to)
            line_item.assign_patient(bounceback_patient)

    def assign_non_bounceback_patients(self):
        for patient in self.get_ordered_non_bounceback_patients_for_assignment():
            line_item=self.get_line_item_moved_furthest_toward_optimal_by_adding_patient(patient)
            line_item.assign_patient(patient)
            pass
            # get line item WITH SPACE for total pt that has next
            # assign patient to line_item

    def assign_all_patients(self):
        self.calculate_optimal_census()
        self.assign_bounceback_patients()
        self.assign_non_bounceback_patients()


class Provider(models.Model):
    abbreviation = models.CharField(max_length=5, unique=True)

    def __str__(self):
        return self.abbreviation


class Census(models.Model):
    total = models.SmallIntegerField(null=True)
    CCU = models.SmallIntegerField(null=True)
    COVID = models.SmallIntegerField(null=True)


class StartingCensus(Census):
    pass


class AssignedCensus(Census):
    pass


class OptimalCensus(models.Model):
    total = models.SmallIntegerField(null=True)
    CCU = models.FloatField(null=True)
    COVID = models.FloatField(null=True)


class FinalCensus(Census):
    pass


class AllocatedCounts(models.Model):
    total_count = models.SmallIntegerField(default=0)
    dual_positive_count = models.SmallIntegerField(default=0)
    ccu_pos_covid_neg_count = models.SmallIntegerField(default=0)
    ccu_neg_covid_pos_count = models.SmallIntegerField(default=0)
    dual_negative_count = models.SmallIntegerField(default=0)


class PatientAssignmentLineItemManager(models.Manager):
    def create_line_item(self, distribution, provider, starting_total, starting_CCU, starting_COVID,
                         position_in_batting_order):
        starting_census = StartingCensus.objects.create(total=starting_total, CCU=starting_CCU, COVID=starting_COVID)
        optimal_census = OptimalCensus.objects.create(total=starting_total, CCU=starting_CCU, COVID=starting_COVID)
        assigned_census = AssignedCensus.objects.create(total=starting_total, CCU=starting_CCU, COVID=starting_COVID)
        # final_census = FinalCensus.objects.create(total=starting_total, CCU=starting_CCU, COVID=starting_COVID)
        allocated_counts = AllocatedCounts.objects.create()
        return super().create(distribution=distribution, provider=provider,
                              position_in_batting_order=position_in_batting_order,
                              starting_census=starting_census, assigned_census=assigned_census,
                              optimal_census=optimal_census,
                              # final_census=final_census,
                              allocated_counts=allocated_counts)


class PatientAssignmentLineItem(models.Model):
    distribution = models.ForeignKey(Distribution, on_delete=models.CASCADE, related_name='line_items')
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    position_in_batting_order = models.SmallIntegerField()
    starting_census = models.ForeignKey(StartingCensus, on_delete=models.CASCADE)
    optimal_census = models.ForeignKey(OptimalCensus, on_delete=models.CASCADE)
    assigned_census = models.ForeignKey(AssignedCensus, on_delete=models.CASCADE)
    allocated_counts = models.ForeignKey(AllocatedCounts, on_delete=models.CASCADE, null=True)
    # final_census = models.ForeignKey(FinalCensus, on_delete=models.CASCADE, null=True)
    affinity_for_COVID_pos_CCU_pos_patients = models.FloatField(default=0)
    count_of_dual_positives_needed_to_fill = models.SmallIntegerField(default=0)

    def assign_patient(self, patient):
        patient.patient_assignment_line_item = self
        patient.save()
        self.assigned_census.total += 1
        if patient.COVID:
            self.assigned_census.COVID += 1
        if patient.CCU:
            self.assigned_census.CCU += 1
        self.assigned_census.save()

    def get_distance_from_assigned_census_to_optimal(self):
        """can think of distance as the linear distance from the current COVID and CCU census to the optimal,
        in effect, the length of the hypotenuse where one side of the triangle is the number of COVIDs needed
        and the other is the number of CCUs.  Could add a third side, total, but will try with how much closer a given
        patient brings the distance"""
        return math.sqrt((self.optimal_census.CCU - self.assigned_census.CCU) ** 2 +
                         (self.optimal_census.COVID - self.assigned_census.COVID) ** 2)

    def get_distance_moved_closer_to_optimal_after_adding_patient(self, patient):
        distance_from_optimal_before_adding_patient = self.get_distance_from_assigned_census_to_optimal()
        distance_from_optimal_after_adding_patient = math.sqrt(
            (self.optimal_census.CCU - self.assigned_census.CCU - int(patient.CCU)) ** 2 +
            (self.optimal_census.COVID - self.assigned_census.COVID - int(patient.COVID)) ** 2
        )
        return distance_from_optimal_before_adding_patient - distance_from_optimal_after_adding_patient
        # def set_line_item_affinity_for_dual_pos_patients(self):
        #     total_room = self.expected_census.total - self.final_census.total
        #     CCU_room = self.expected_census.CCU - self.final_census.CCU
        #     COVID_room = self.expected_census.COVID - self.final_census.COVID
        #     if total_room <= 0 or CCU_room <= 0 or COVID_room <= 0:
        #         self.affinity_for_COVID_pos_CCU_pos_patients = 0
        #     else:
        #         self.affinity_for_COVID_pos_CCU_pos_patients = (COVID_room + CCU_room) / (2 * total_room)
        #     self.save()
        #
        # def get_proposed_census(self, patient):  # census after adding a given patient
        #     return {'total': 1 + self.assigned_census.total, 'CCU': patient.CCU + self.assigned_census.CCU,
        #             'COVID': patient.COVID + self.assigned_census.COVID}
        #
        # def get_std_dev_of_given_census_from_optimal_census(self, ccu_census, covid_census):
        #     return math.sqrt(
        #         ((ccu_census - self.optimal_census.CCU) / (2 * self.optimal_census.CCU)) ** 2 +
        #         ((covid_census - self.optimal_census.COVID) / (2 * self.optimal_census.COVID)) ** 2)

        # def get_improvement_in_std_dev_from_assigned_census_after_patient_added(self, patient):
        #     proposed_census = self.get_proposed_census(patient=patient)
        #
        #     std_dev_improvement = self.get_std_dev_of_given_census_from_optimal_census(
        #         ccu_census=proposed_census['CCU'], covid_census=proposed_census['COVID']) - \
        #                           self.get_std_dev_of_given_census_from_optimal_census(
        #                               ccu_census=self.assigned_census.CCU, covid_census=self.assigned_census.COVID)
        return std_dev_improvement

    objects = PatientAssignmentLineItemManager()


class Patient(models.Model):
    distribution = models.ForeignKey(Distribution, on_delete=models.CASCADE)
    number_designation = models.SmallIntegerField()
    CCU = models.BooleanField(default=False)
    COVID = models.BooleanField(default=False)
    bounce_to = models.ForeignKey(Provider, blank=True, null=True, on_delete=models.CASCADE)
    patient_assignment_line_item = models.ForeignKey(PatientAssignmentLineItem, blank=True, null=True,
                                                     on_delete=models.CASCADE, related_name='assigned_patients')
