import React from 'react';

const Book = ({ 
  coverImage, 
  title, 
  author, 
  isbn10, 
  isbn13, 
  genres, 
  yearOfPublication, 
  numberOfPages, 
  averageRating, 
  numberOfRatings 
}) => (
  <tr>
    <td>
      {coverImage && (
        <img
          src={coverImage}
          alt={title}
          className="book-cover"
          onError={(e) => {
            e.target.src = '/placeholder-book.png';
            e.target.onerror = null;
          }}
        />
      )}
    </td>
    <td>{title}</td>
    <td>{author}</td>
    <td>{isbn10}</td>
    <td>{isbn13}</td>
    <td>{genres}</td>
    <td>{yearOfPublication}</td>
    <td>{numberOfPages}</td>
    <td>{averageRating?.toFixed(1)}</td>
    <td>{numberOfRatings}</td>
  </tr>
);

export default Book;