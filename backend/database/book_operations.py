from sqlalchemy import or_
from database.genre import Genre
from database.genre_operations import filter_books_by_genres, update_book_genres
from database.book import db, Book, book_genres
from database.user import favorite_books
from database.audit import AuditEventType
from database.audit_operations import create_audit_log
from sqlalchemy.exc import SQLAlchemyError

def get_favorite_books(user_id, page=1, per_page=25):
    try:
        base_query = db.session.query(Book).join(
            favorite_books,
            Book.ISBN10 == favorite_books.c.book_isbn10
        ).filter(
            favorite_books.c.user_id == user_id
        )

        total_books = base_query.count()
        books = base_query.order_by(Book.Title).offset((page - 1) * per_page).limit(per_page).all()

        books_data = _format_books_data(books)
        return books_data, total_books
    except SQLAlchemyError as e:
        print(f"Error getting favorite books: {str(e)}")
        return [], 0

def search_books(title=None, authors=None, isbn=None, genres=None, page=1, per_page=25):
    try:
        query = Book.query.filter_by(is_visible=True)

        if title:
            query = query.filter(Book.Title.ilike(f'%{title}%'))

        if authors:
            author_terms = [author.strip() for author in authors.split(';') if author.strip()]
            for author in author_terms:
                query = query.filter(Book.Author.ilike(f'%{author}%'))

        if isbn:
            query = query.filter(
                or_(
                    Book.ISBN10.ilike(f'%{isbn}%'),
                    Book.ISBN13.ilike(f'%{isbn}%')
                )
            )

        if genres:
            query = filter_books_by_genres(query, genres)

        total = query.count()
        books = query.order_by(Book.Title).offset((page - 1) * per_page).limit(per_page).all()

        books_data = _format_books_data(books)
        return books_data, total
    except SQLAlchemyError as e:
        print(f"Error searching books: {str(e)}")
        return [], 0

def get_book_by_isbn(isbn, user_id=None):
    try:
        book = Book.query.filter(
            (Book.ISBN10 == isbn) | (Book.ISBN13 == isbn)
        ).filter_by(is_visible=True).first()

        if not book:
            return None

        is_favorite = False
        if user_id:
            favorite = db.session.query(favorite_books).filter_by(
                user_id=user_id,
                book_isbn10=book.ISBN10
            ).first()
            is_favorite = favorite is not None

        return _format_book_data(book, is_favorite)
    except SQLAlchemyError as e:
        print(f"Error getting book by ISBN: {str(e)}")
        return None

def fetch_and_update_books(books_data):
    try:
        previously_visible_books = {book.ISBN10 for book in Book.query.filter_by(is_visible=True).all()}
        new_visible_isbns = {book['isbn10'] for book in books_data if book.get('isbn10')}
        newly_added_books = set()
        
        updated_books = 0
        new_books = 0
        
        Book.query.update({Book.is_visible: False}, synchronize_session=False)
        
        for book in books_data:
            isbn10 = book.get('isbn10')
            if not isbn10:
                continue

            existing_book = Book.query.get(isbn10)
            categories = book.get('categories', '')  # Získáme žánry z dat knihy

            if existing_book:
                _update_existing_book(existing_book, book)
                update_book_genres(existing_book, categories)  # Aktualizujeme žánry
                updated_books += 1
            else:
                new_book = _create_new_book(book)
                update_book_genres(new_book, categories)  # Nastavíme žánry
                db.session.add(new_book)
                new_books += 1
                newly_added_books.add(isbn10)

                # Záznam o přidání nové knihy - už bez book_title
                create_audit_log(
                    event_type=AuditEventType.BOOK_ADD,
                    username="CDB_SYSTEM",
                    book_isbn=isbn10,
                    additional_data={
                        "author": new_book.Author
                    }
                )

        _create_audit_logs(previously_visible_books, new_visible_isbns, newly_added_books)

        db.session.commit()
        return updated_books, new_books

    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def _format_books_data(books):
    return [{
        'ISBN10': book.ISBN10,
        'ISBN13': book.ISBN13,
        'Title': book.Title,
        'Author': book.Author,
        'Genres': [genre.name for genre in book.genres],  # Seznam názvů žánrů
        'Cover_Image': book.Cover_Image,
        'Description': book.Description,
        'Year_of_Publication': book.Year_of_Publication,
        'Number_of_Pages': book.Number_of_Pages,
        'Average_Rating': book.Average_Rating,
        'Number_of_Ratings': book.Number_of_Ratings,
        'Price': book.Price,
        'is_visible': book.is_visible
    } for book in books]

def _format_book_data(book, is_favorite=False):
    return {
        'ISBN10': book.ISBN10,
        'ISBN13': book.ISBN13,
        'Title': book.Title,
        'Author': book.Author,
        'Genres': [genre.name for genre in book.genres],  # Seznam názvů žánrů
        'Cover_Image': book.Cover_Image,
        'Description': book.Description,
        'Year_of_Publication': book.Year_of_Publication,
        'Number_of_Pages': book.Number_of_Pages,
        'Average_Rating': book.Average_Rating,
        'Number_of_Ratings': book.Number_of_Ratings,
        'Price': book.Price,
        'is_favorite': is_favorite
    }

def _update_existing_book(book, data):
    book.is_visible = data.get('price', 0) > 0
    book.ISBN13 = data.get('isbn13')
    book.Title = data.get('title')
    book.Author = data.get('authors') if isinstance(data.get('authors'), str) else '; '.join(data.get('authors', []))
    book.Cover_Image = data.get('thumbnail')
    book.Description = data.get('description')
    book.Year_of_Publication = data.get('published_year')
    book.Number_of_Pages = data.get('num_pages')
    book.Average_Rating = data.get('average_rating')
    book.Number_of_Ratings = data.get('ratings_count')
    book.Price = data.get('price')

def _create_new_book(data):
    return Book(
        ISBN10=data.get('isbn10'),
        ISBN13=data.get('isbn13'),
        Title=data.get('title'),
        Author=data.get('authors') if isinstance(data.get('authors'), str) else '; '.join(data.get('authors', [])),
        Cover_Image=data.get('thumbnail'),
        Description=data.get('description'),
        Year_of_Publication=data.get('published_year'),
        Number_of_Pages=data.get('num_pages'),
        Average_Rating=data.get('average_rating'),
        Number_of_Ratings=data.get('ratings_count'),
        Price=data.get('price'),
        is_visible=data.get('price', 0) > 0
        # Žánry se nastavují zvlášť pomocí update_book_genres
    )


def _create_audit_logs(previously_visible_books, new_visible_isbns, newly_added_books):
    # Zaznamenání skrytých knih
    for isbn in previously_visible_books:
        if isbn not in new_visible_isbns:
            create_audit_log(
                event_type=AuditEventType.BOOK_HIDE,
                username="CDB_SYSTEM",
                book_isbn=isbn
            )

    for isbn in new_visible_isbns:
        if isbn not in previously_visible_books and isbn not in newly_added_books:
            book = Book.query.get(isbn)
            if book:
                create_audit_log(
                    event_type=AuditEventType.BOOK_SHOW,
                    username="CDB_SYSTEM",
                    book_isbn=isbn
                )

def get_all_unique_genres():
    """
    Získá všechny unikátní žánry z aktivních knih.
    
    Returns:
        List[str]: Seřazený seznam názvů žánrů
    """
    try:
        # Získáme všechny žánry, které mají alespoň jednu viditelnou knihu
        active_genres = Genre.query\
            .join(book_genres)\
            .join(Book)\
            .filter(Book.is_visible == True)\
            .distinct()\
            .order_by(Genre.name)\
            .all()

        return [genre.name for genre in active_genres]
    except SQLAlchemyError as e:
        print(f"Error getting unique genres: {str(e)}")
        return []
