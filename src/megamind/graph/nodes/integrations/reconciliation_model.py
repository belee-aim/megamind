# merge_customers_bank.py


def merge_customer_data(formatted_bank_data, customers_data):
    # Step 1: Merge on bank_account_no (left join)
    merge_by_bank_no = formatted_bank_data.merge(
        customers_data[customers_data['bank_account_no'].notnull()],
        how='left',
        left_on='FromAccount',
        right_on='bank_account_no',
        suffixes=('', '_bank_no')
    )

    # Step 2: Merge on IBAN (left join)
    merge_by_iban = formatted_bank_data.merge(
        customers_data[customers_data['iban'].notnull()],
        how='left',
        left_on='FromAccount',
        right_on='iban',
        suffixes=('', '_iban')
    )

    # Step 3: Combine both
    final_df = merge_by_bank_no.combine_first(merge_by_iban)
    final_df.reset_index(drop=True, inplace=True)

    # Optional: Add match_type
    final_df['match_type'] = final_df['bank_account_no'].notna().map({True: 'bank_account_no', False: 'iban'})
    
    return final_df