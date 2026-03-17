from django.core.management.base import BaseCommand
from datetime import date, datetime
from question_solver.models import DailyQuiz, DailyQuestion
import random


class Command(BaseCommand):
    help = 'Generate daily GK quiz with 10 questions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date for the quiz (YYYY-MM-DD). Defaults to today.'
        )

    def handle(self, *args, **options):
        quiz_date_str = options.get('date')
        if quiz_date_str:
            try:
                quiz_date = datetime.strptime(quiz_date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            quiz_date = date.today()

        if DailyQuiz.objects.filter(date=quiz_date).exists():
            self.stdout.write(self.style.WARNING(f'Quiz already exists for {quiz_date}'))
            return

        daily_quiz = DailyQuiz.objects.create(
            date=quiz_date,
            title=f'Daily GK Quiz - {quiz_date.strftime("%B %d, %Y")}',
            description='Test your general knowledge with 10 interesting questions!',
            difficulty='mixed',
            total_questions=10,
            coins_per_correct=5,
            is_active=True
        )

        # Sample questions pool (easy to moderate GK questions)
        # In production, you'd fetch these from a database or API
        questions_pool = [
            # Easy Questions
            {
                'question_text': 'What is the capital of France?',
                'category': 'geography',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'London'},
                    {'id': 'B', 'text': 'Paris'},
                    {'id': 'C', 'text': 'Berlin'},
                    {'id': 'D', 'text': 'Madrid'}
                ],
                'correct_answer': 'B',
                'explanation': 'Paris is the capital and most populous city of France.',
                'fun_fact': 'Paris is known as "The City of Light" (La Ville Lumière).'
            },
            {
                'question_text': 'How many continents are there on Earth?',
                'category': 'geography',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': '5'},
                    {'id': 'B', 'text': '6'},
                    {'id': 'C', 'text': '7'},
                    {'id': 'D', 'text': '8'}
                ],
                'correct_answer': 'C',
                'explanation': 'There are 7 continents: Asia, Africa, North America, South America, Antarctica, Europe, and Australia.',
                'fun_fact': 'Asia is the largest continent covering about 30% of Earth\'s land area.'
            },
            {
                'question_text': 'What is the largest ocean on Earth?',
                'category': 'geography',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'Atlantic Ocean'},
                    {'id': 'B', 'text': 'Indian Ocean'},
                    {'id': 'C', 'text': 'Arctic Ocean'},
                    {'id': 'D', 'text': 'Pacific Ocean'}
                ],
                'correct_answer': 'D',
                'explanation': 'The Pacific Ocean is the largest ocean, covering more than 30% of Earth\'s surface.',
                'fun_fact': 'The Pacific Ocean contains about 25,000 islands!'
            },
            {
                'question_text': 'Who wrote the play "Romeo and Juliet"?',
                'category': 'general',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'Charles Dickens'},
                    {'id': 'B', 'text': 'William Shakespeare'},
                    {'id': 'C', 'text': 'Jane Austen'},
                    {'id': 'D', 'text': 'Mark Twain'}
                ],
                'correct_answer': 'B',
                'explanation': 'William Shakespeare wrote Romeo and Juliet around 1594-1596.',
                'fun_fact': 'Shakespeare invented over 1,700 words we still use today!'
            },
            {
                'question_text': 'What is the speed of light approximately?',
                'category': 'science',
                'difficulty': 'moderate',
                'options': [
                    {'id': 'A', 'text': '300,000 km/s'},
                    {'id': 'B', 'text': '150,000 km/s'},
                    {'id': 'C', 'text': '500,000 km/s'},
                    {'id': 'D', 'text': '1,000,000 km/s'}
                ],
                'correct_answer': 'A',
                'explanation': 'The speed of light in vacuum is approximately 299,792 km/s (often rounded to 300,000 km/s).',
                'fun_fact': 'Light from the Sun takes about 8 minutes to reach Earth.'
            },
            # Moderate Questions
            {
                'question_text': 'In which year did World War II end?',
                'category': 'history',
                'difficulty': 'moderate',
                'options': [
                    {'id': 'A', 'text': '1943'},
                    {'id': 'B', 'text': '1944'},
                    {'id': 'C', 'text': '1945'},
                    {'id': 'D', 'text': '1946'}
                ],
                'correct_answer': 'C',
                'explanation': 'World War II ended in 1945 with Germany surrendering in May and Japan in September.',
                'fun_fact': 'VE Day (Victory in Europe) was celebrated on May 8, 1945.'
            },
            {
                'question_text': 'What is the smallest prime number?',
                'category': 'science',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': '0'},
                    {'id': 'B', 'text': '1'},
                    {'id': 'C', 'text': '2'},
                    {'id': 'D', 'text': '3'}
                ],
                'correct_answer': 'C',
                'explanation': '2 is the smallest prime number and the only even prime number.',
                'fun_fact': 'There are infinitely many prime numbers!'
            },
            {
                'question_text': 'Which planet is known as the "Red Planet"?',
                'category': 'science',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'Venus'},
                    {'id': 'B', 'text': 'Mars'},
                    {'id': 'C', 'text': 'Jupiter'},
                    {'id': 'D', 'text': 'Saturn'}
                ],
                'correct_answer': 'B',
                'explanation': 'Mars is called the Red Planet because of iron oxide (rust) on its surface.',
                'fun_fact': 'Mars has the largest volcano in our solar system - Olympus Mons!'
            },
            {
                'question_text': 'Who painted the Mona Lisa?',
                'category': 'general',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'Vincent van Gogh'},
                    {'id': 'B', 'text': 'Pablo Picasso'},
                    {'id': 'C', 'text': 'Leonardo da Vinci'},
                    {'id': 'D', 'text': 'Michelangelo'}
                ],
                'correct_answer': 'C',
                'explanation': 'Leonardo da Vinci painted the Mona Lisa between 1503-1519.',
                'fun_fact': 'The Mona Lisa has no visible eyebrows - it was fashionable to shave them in Renaissance Florence!'
            },
            {
                'question_text': 'What is the largest mammal in the world?',
                'category': 'science',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'African Elephant'},
                    {'id': 'B', 'text': 'Blue Whale'},
                    {'id': 'C', 'text': 'Giraffe'},
                    {'id': 'D', 'text': 'Polar Bear'}
                ],
                'correct_answer': 'B',
                'explanation': 'The Blue Whale is the largest mammal, reaching up to 100 feet in length.',
                'fun_fact': 'A Blue Whale\'s heart is the size of a small car!'
            },
            {
                'question_text': 'Which country hosted the 2024 Summer Olympics?',
                'category': 'current_events',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'Japan'},
                    {'id': 'B', 'text': 'China'},
                    {'id': 'C', 'text': 'France'},
                    {'id': 'D', 'text': 'USA'}
                ],
                'correct_answer': 'C',
                'explanation': 'Paris, France hosted the 2024 Summer Olympics (July 26 - August 11, 2024).',
                'fun_fact': 'This was Paris\'s third time hosting the Olympics (1900, 1924, 2024).'
            },
            {
                'question_text': 'What is the currency of Japan?',
                'category': 'geography',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'Yuan'},
                    {'id': 'B', 'text': 'Won'},
                    {'id': 'C', 'text': 'Yen'},
                    {'id': 'D', 'text': 'Rupee'}
                ],
                'correct_answer': 'C',
                'explanation': 'The Japanese Yen (¥) is the official currency of Japan.',
                'fun_fact': 'The yen symbol (¥) is also used for the Chinese yuan.'
            },
            {
                'question_text': 'How many players are in a soccer/football team on the field?',
                'category': 'sports',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': '9'},
                    {'id': 'B', 'text': '10'},
                    {'id': 'C', 'text': '11'},
                    {'id': 'D', 'text': '12'}
                ],
                'correct_answer': 'C',
                'explanation': 'Each soccer team has 11 players on the field, including the goalkeeper.',
                'fun_fact': 'The earliest forms of soccer date back over 2,000 years to ancient China!'
            },
            {
                'question_text': 'What is the chemical symbol for gold?',
                'category': 'science',
                'difficulty': 'moderate',
                'options': [
                    {'id': 'A', 'text': 'Go'},
                    {'id': 'B', 'text': 'Au'},
                    {'id': 'C', 'text': 'Gd'},
                    {'id': 'D', 'text': 'Gl'}
                ],
                'correct_answer': 'B',
                'explanation': 'Au comes from the Latin word "aurum" meaning gold.',
                'fun_fact': 'All the gold ever mined would fit into a cube about 21 meters on each side!'
            },
            {
                'question_text': 'Which social media platform uses a bird as its logo?',
                'category': 'technology',
                'difficulty': 'easy',
                'options': [
                    {'id': 'A', 'text': 'Facebook'},
                    {'id': 'B', 'text': 'Instagram'},
                    {'id': 'C', 'text': 'Twitter/X'},
                    {'id': 'D', 'text': 'Snapchat'}
                ],
                'correct_answer': 'C',
                'explanation': 'Twitter (now X) originally used a blue bird as its logo.',
                'fun_fact': 'The Twitter bird has a name - Larry, named after basketball player Larry Bird!'
            },
        ]

        # Randomly select 10 questions (mix of easy and moderate)
        selected_questions = random.sample(questions_pool, min(10, len(questions_pool)))

        # Create questions
        for idx, q_data in enumerate(selected_questions, start=1):
            DailyQuestion.objects.create(
                daily_quiz=daily_quiz,
                order=idx,
                question_text=q_data['question_text'],
                category=q_data['category'],
                difficulty=q_data['difficulty'],
                options=q_data['options'],
                correct_answer=q_data['correct_answer'],
                explanation=q_data.get('explanation', ''),
                fun_fact=q_data.get('fun_fact', ''),
            )

        self.stdout.write(self.style.SUCCESS(
            f'Successfully created Daily Quiz for {quiz_date} with {len(selected_questions)} questions'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Max coins: {daily_quiz.max_coins}'
        ))
