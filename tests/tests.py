import os
import csv
from datetime import date
from .models import (
    MockObject,
    MockBlankObject,
    ExtendedMockObject,
    LimitedMockObject,
    OverloadMockObject,
    HookedCopyMapping
)
from django.db.models import Count
from postgres_copy import CopyMapping
from django.test import TestCase


class BaseTest(TestCase):

    def setUp(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.name_path = os.path.join(self.data_dir, 'names.csv')
        self.foreign_path = os.path.join(self.data_dir, 'foreignkeys.csv')
        self.pipe_path = os.path.join(self.data_dir, 'pipes.csv')
        self.quote_path = os.path.join(self.data_dir, 'quote.csv')
        self.blank_null_path = os.path.join(self.data_dir, 'blanknulls.csv')
        self.null_path = os.path.join(self.data_dir, 'nulls.csv')
        self.backwards_path = os.path.join(self.data_dir, 'backwards.csv')

    def tearDown(self):
        MockObject.objects.all().delete()
        ExtendedMockObject.objects.all().delete()
        LimitedMockObject.objects.all().delete()
        OverloadMockObject.objects.all().delete()


class PostgresCopyToTest(BaseTest):

    def setUp(self):
        super(PostgresCopyToTest, self).setUp()
        self.export_path = os.path.join(os.path.dirname(__file__), 'export.csv')

    def tearDown(self):
        super(PostgresCopyToTest, self).tearDown()
        if os.path.exists(self.export_path):
            os.remove(self.export_path)

    def _load_objects(self, file_path, mapping=dict(name='NAME', number='NUMBER', dt='DATE')):
        MockObject.objects.from_csv(file_path, mapping)

    def test_export(self):
        self._load_objects(self.name_path)
        MockObject.objects.to_csv(self.export_path)
        self.assertTrue(os.path.exists(self.export_path))
        reader = csv.DictReader(open(self.export_path, 'r'))
        self.assertTrue(
            ['BEN', 'JOE', 'JANE'],
            [i['name'] for i in reader]
        )

    def test_filter(self):
        self._load_objects(self.name_path)
        MockObject.objects.filter(name="BEN").to_csv(self.export_path)
        reader = csv.DictReader(open(self.export_path, 'r'))
        self.assertTrue(
            ['BEN'],
            [i['name'] for i in reader]
        )

    def test_fewer_fields(self):
        self._load_objects(self.name_path)
        MockObject.objects.to_csv(self.export_path, 'name')
        reader = csv.DictReader(open(self.export_path, 'r'))
        for row in reader:
            self.assertTrue(row['name'] in ['BEN', 'JOE', 'JANE'])
            self.assertTrue(len(row.keys()), 1)

    def test_related_fields(self):
        self._load_objects(
            self.foreign_path,
            mapping=dict(name='NAME', number='NUMBER', dt='DATE', parent='PARENT')
        )
        MockObject.objects.to_csv(self.export_path, 'name', 'parent__id', 'parent__name')
        reader = csv.DictReader(open(self.export_path, 'r'))
        for row in reader:
            self.assertTrue(row['parent_id'] in ['4', '5', '6'])
            self.assertTrue(len(row.keys()), 3)

    def test_annotate(self):
        self._load_objects(self.name_path)
        MockObject.objects.annotate(name_count=Count('name')).to_csv(self.export_path)
        reader = csv.DictReader(open(self.export_path, 'r'))
        for row in reader:
            self.assertTrue('name_count' in row)

    def test_extra(self):
        self._load_objects(self.name_path)
        MockObject.objects.extra(select={'lower': 'LOWER("name")'}).to_csv(self.export_path)
        reader = csv.DictReader(open(self.export_path, 'r'))
        for row in reader:
            self.assertTrue('lower' in row)


class PostgresCopyTest(BaseTest):

    def test_bad_call(self):
        with self.assertRaises(TypeError):
            CopyMapping()

    def test_bad_csv(self):
        with self.assertRaises(ValueError):
            CopyMapping(
                MockObject,
                '/foobar.csv',
                dict(name='NAME', number='NUMBER', dt='DATE'),
                using='sqlite'
            )

    def test_bad_backend(self):
        with self.assertRaises(TypeError):
            CopyMapping(
                MockObject,
                self.name_path,
                dict(name='NAME', number='NUMBER', dt='DATE'),
                using='sqlite'
            )

    def test_bad_header(self):
        with self.assertRaises(ValueError):
            CopyMapping(
                MockObject,
                self.name_path,
                dict(name='NAME1', number='NUMBER', dt='DATE'),
            )

    def test_bad_field(self):
        with self.assertRaises(ValueError):
            CopyMapping(
                MockObject,
                self.name_path,
                dict(name1='NAME', number='NUMBER', dt='DATE'),
            )

    def test_limited_fields(self):
        CopyMapping(
            LimitedMockObject,
            self.name_path,
            dict(name='NAME', dt='DATE'),
        )

    def test_simple_save(self):
        MockObject.objects.from_csv(
            self.name_path,
            dict(name='NAME', number='NUMBER', dt='DATE')
        )
        self.assertEqual(MockObject.objects.count(), 3)
        self.assertEqual(MockObject.objects.get(name='BEN').number, 1)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_limited_save(self):
        LimitedMockObject.objects.from_csv(
            self.name_path,
            dict(name='NAME', dt='DATE')
        )
        self.assertEqual(LimitedMockObject.objects.count(), 3)
        self.assertEqual(
            LimitedMockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_save_foreign_key(self):
        MockObject.objects.from_csv(
            self.foreign_path,
            dict(name='NAME', number='NUMBER', dt='DATE', parent='PARENT')
        )
        self.assertEqual(MockObject.objects.count(), 3)
        self.assertEqual(MockObject.objects.get(name='BEN').parent_id, 4)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_save_foreign_key_by_id(self):
        MockObject.objects.from_csv(
            self.foreign_path,
            dict(name='NAME', number='NUMBER', dt='DATE', parent_id='PARENT')
        )
        self.assertEqual(MockObject.objects.count(), 3)
        self.assertEqual(MockObject.objects.get(name='BEN').parent_id, 4)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_silent_save(self):
        c = CopyMapping(
            MockObject,
            self.name_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
        )
        c.save(silent=True)
        self.assertEqual(MockObject.objects.count(), 3)
        self.assertEqual(MockObject.objects.get(name='BEN').number, 1)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_pipe_save(self):
        MockObject.objects.from_csv(
            self.pipe_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
            delimiter="|",
        )
        self.assertEqual(MockObject.objects.count(), 3)
        self.assertEqual(MockObject.objects.get(name='BEN').number, 1)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_quote_save(self):
        MockObject.objects.from_csv(
            self.quote_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
            delimiter="\t",
            quote_character='`'
        )
        self.assertEqual(MockObject.objects.count(), 3)
        self.assertEqual(MockObject.objects.get(number=1).name, 'B`EN')
        self.assertEqual(MockObject.objects.get(number=2).name, 'JO\tE')
        self.assertEqual(MockObject.objects.get(number=3).name, 'JAN"E')

    def test_null_save(self):
        MockObject.objects.from_csv(
            self.null_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
            null='',
        )
        self.assertEqual(MockObject.objects.count(), 5)
        self.assertEqual(MockObject.objects.get(name='BEN').number, 1)
        self.assertEqual(MockObject.objects.get(name='NULLBOY').number, None)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_force_not_null_save(self):
        MockBlankObject.objects.from_csv(
            self.blank_null_path,
            dict(name='NAME', number='NUMBER', dt='DATE', color='COLOR'),
            force_not_null=('COLOR',),
        )
        self.assertEqual(MockBlankObject.objects.count(), 5)
        self.assertEqual(MockBlankObject.objects.get(name='BEN').color, 'red')
        self.assertEqual(MockBlankObject.objects.get(name='NULLBOY').color, '')
        self.assertEqual(
            MockBlankObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_force_null_save(self):
        MockObject.objects.from_csv(
            self.null_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
            force_null=('NUMBER',),
        )
        self.assertEqual(MockObject.objects.count(), 5)
        self.assertEqual(MockObject.objects.get(name='BEN').number, 1)
        self.assertEqual(MockObject.objects.get(name='NULLBOY').number, None)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_backwards_save(self):
        MockObject.objects.from_csv(
            self.backwards_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
        )
        self.assertEqual(MockObject.objects.count(), 3)
        self.assertEqual(MockObject.objects.get(name='BEN').number, 1)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_field_override_save(self):
        MockObject.objects.from_csv(
            self.null_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
        )
        self.assertEqual(MockObject.objects.count(), 5)
        self.assertEqual(MockObject.objects.get(name='BADBOY').number, None)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_encoding_save(self):
        MockObject.objects.from_csv(
            self.null_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
            encoding='UTF-8'
        )
        self.assertEqual(MockObject.objects.count(), 5)
        self.assertEqual(MockObject.objects.get(name='BADBOY').number, None)
        self.assertEqual(
            MockObject.objects.get(name='BEN').dt,
            date(2012, 1, 1)
        )

    def test_static_values(self):
        ExtendedMockObject.objects.from_csv(
            self.name_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
            static_mapping=dict(static_val=1, static_string='test')
        )
        self.assertEqual(
            ExtendedMockObject.objects.filter(static_val=1).count(),
            3
        )
        self.assertEqual(
            ExtendedMockObject.objects.filter(static_string='test').count(),
            3
        )

    def test_bad_static_values(self):
        with self.assertRaises(ValueError):
            ExtendedMockObject.objects.from_csv(
                self.name_path,
                dict(name='NAME', number='NUMBER', dt='DATE'),
                encoding='UTF-8',
                static_mapping=dict(static_bad=1)
            )

    def test_overload_save(self):
        OverloadMockObject.objects.from_csv(
            self.name_path,
            dict(name='NAME', lower_name='NAME', upper_name='NAME', number='NUMBER', dt='DATE'),
        )
        self.assertEqual(OverloadMockObject.objects.count(), 3)
        self.assertEqual(OverloadMockObject.objects.get(name='ben').number, 1)
        self.assertEqual(OverloadMockObject.objects.get(lower_name='ben').number, 1)
        self.assertEqual(OverloadMockObject.objects.get(upper_name='BEN').number, 1)
        self.assertEqual(
            OverloadMockObject.objects.get(name='ben').dt,
            date(2012, 1, 1)
        )
        omo = OverloadMockObject.objects.first()
        self.assertEqual(omo.name.lower(), omo.lower_name)

    def test_missing_overload_field(self):
        with self.assertRaises(ValueError):
            CopyMapping(
                OverloadMockObject,
                self.name_path,
                dict(name='NAME', number='NUMBER', dt='DATE', missing='NAME'),
            )

    def test_save_steps(self):
        c = CopyMapping(
            MockObject,
            self.name_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
        )
        cursor = c.conn.cursor()

        c.create(cursor)
        cursor.execute("""SELECT count(*) FROM %s;""" % c.temp_table_name)
        self.assertEquals(cursor.fetchone()[0], 0)
        cursor.execute("""SELECT count(*) FROM %s;""" % c.model._meta.db_table)
        self.assertEquals(cursor.fetchone()[0], 0)

        c.copy(cursor)
        cursor.execute("""SELECT count(*) FROM %s;""" % c.temp_table_name)
        self.assertEquals(cursor.fetchone()[0], 3)
        cursor.execute("""SELECT count(*) FROM %s;""" % c.model._meta.db_table)
        self.assertEquals(cursor.fetchone()[0], 0)

        c.insert(cursor)
        cursor.execute("""SELECT count(*) FROM %s;""" % c.model._meta.db_table)
        self.assertEquals(cursor.fetchone()[0], 3)

        c.drop(cursor)
        self.assertEquals(cursor.statusmessage, 'DROP TABLE')
        cursor.close()

    def test_hooks(self):
        c = HookedCopyMapping(
            MockObject,
            self.name_path,
            dict(name='NAME', number='NUMBER', dt='DATE'),
        )
        cursor = c.conn.cursor()

        c.create(cursor)
        self.assertRaises(AttributeError, lambda: c.ran_pre_copy)
        self.assertRaises(AttributeError, lambda: c.ran_post_copy)
        self.assertRaises(AttributeError, lambda: c.ran_pre_insert)
        self.assertRaises(AttributeError, lambda: c.ran_post_insert)

        c.copy(cursor)
        self.assertTrue(c.ran_pre_copy)
        self.assertTrue(c.ran_post_copy)
        self.assertRaises(AttributeError, lambda: c.ran_pre_insert)
        self.assertRaises(AttributeError, lambda: c.ran_post_insert)

        c.insert(cursor)
        self.assertTrue(c.ran_pre_copy)
        self.assertTrue(c.ran_post_copy)
        self.assertTrue(c.ran_pre_insert)
        self.assertTrue(c.ran_post_insert)

        c.drop(cursor)
        cursor.close()
