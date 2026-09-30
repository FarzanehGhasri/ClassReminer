-- Sample data, loaded only on first start of an empty volume.
-- Safe to delete this file if you would rather start with an empty database.

BEGIN;

INSERT INTO student (first_name, last_name, phone_number, email, bale_chat_id) VALUES
    ('درسا',    'قصری',      '+989122025452', 'farzanehghasri.dorsa@gmail.com', '1876190191'),
    ('مهزیار',  'گیلانپور',  '+989385818976', 'mgillanpour79@gmail.com',        '194964895'),
    ('زهرا',    'محمدی',     '+989121234567', 'zahra.mohammadi@example.com',    NULL),
    ('علی',     'رضایی',     '+989351112233', 'ali.rezaei@example.com',         NULL),
    ('نیلوفر',  'حسین‌زاده',  '+989309998877', 'niloofar.h@example.com',         NULL);

-- A private online class, a group online class, and an in-person class.
INSERT INTO class (class_day, class_time, class_link, delivery_mode, class_format) VALUES
    ('wednesday', '12:45', 'https://meet.google.com/syz-yiwi-tmv', 'online',    'private'),
    ('wednesday', '17:30', 'https://meet.google.com/abc-defg-hij', 'online',    'group'),
    ('saturday',  '10:00', NULL,                                   'in_person', 'group');

-- درسا has the private slot to herself.
INSERT INTO student_class (student_id, class_id) VALUES (1, 1);

-- The group slots are shared — the same class_id against several students,
-- which is exactly what the bridge table is for.
INSERT INTO student_class (student_id, class_id) VALUES (2, 2), (3, 2), (4, 2);
INSERT INTO student_class (student_id, class_id) VALUES (4, 3), (5, 3);

COMMIT;
